"""Short-interval target price forecasts for commodity dashboards."""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

from analytics.candlestick_patterns import (
    calculate_support_resistance,
    detect_candlestick_patterns,
)
from analytics.volume_detector import (
    detect_open_interest_anomaly,
    detect_volume_anomaly,
)


FORECAST_INTERVALS: List[Tuple[str, int]] = [
    ("15 mins", 15),
    ("30 mins", 30),
    ("45 mins", 45),
    ("1 hr", 60),
    ("2 hr", 120),
    ("3 hr", 180),
    ("4 hr", 240),
    ("5 hr", 300),
]


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _latest(series: pd.Series, default: float = 0.0) -> float:
    if series is None or len(series) == 0:
        return default
    return _safe_float(series.iloc[-1], default)


def _clip(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _pattern_bias(pattern_signal: str, confidence: float) -> float:
    strength = _clip(confidence / 100.0, 0.0, 1.0)
    if pattern_signal == "BUY_CALL":
        return 0.0009 * strength
    if pattern_signal == "BUY_PUT":
        return -0.0009 * strength
    return 0.0


def _technical_bias(data: pd.DataFrame, close_col: str) -> float:
    close = _latest(data[close_col])
    if close <= 0:
        return 0.0

    sma_10 = _latest(data.get("SMA_10", pd.Series(dtype=float)), close)
    sma_20 = _latest(data.get("SMA_20", pd.Series(dtype=float)), close)
    rsi = _latest(data.get("RSI_14", pd.Series(dtype=float)), 50.0)
    macd = _latest(data.get("MACD", pd.Series(dtype=float)), 0.0)
    macd_signal = _latest(data.get("MACD_Signal", pd.Series(dtype=float)), 0.0)

    trend_bias = _clip((sma_10 - sma_20) / close, -0.0012, 0.0012)
    rsi_bias = _clip((50.0 - rsi) / 50.0, -1.0, 1.0) * 0.00035
    macd_bias = _clip((macd - macd_signal) / close, -0.0006, 0.0006)
    return trend_bias + rsi_bias + macd_bias


def _momentum_bias(data: pd.DataFrame, close_col: str) -> float:
    close = data[close_col].dropna()
    if len(close) < 3:
        return 0.0

    returns = close.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty:
        return 0.0

    fast = returns.tail(3).mean()
    medium = returns.tail(min(12, len(returns))).mean()
    return _clip((fast * 0.65) + (medium * 0.35), -0.003, 0.003)


def _sentiment_bias(sentiment_data: Optional[Dict]) -> float:
    if not sentiment_data:
        return 0.0
    sentiment = _safe_float(sentiment_data.get("overall_sentiment"), 0.0)
    confidence = _clip(_safe_float(sentiment_data.get("confidence"), 0.0) / 100.0, 0.0, 1.0)
    return _clip(sentiment, -1.0, 1.0) * confidence * 0.0008


def _open_interest_bias(data: pd.DataFrame) -> Tuple[float, Dict]:
    oi_col = next(
        (col for col in ["Open Interest", "OpenInterest", "OI", "open_interest"] if col in data.columns),
        None,
    )
    if not oi_col:
        return 0.0, {
            "oi_trend": "UNAVAILABLE",
            "oi_change_pct": 0.0,
            "oi_momentum": 0.0,
        }

    oi_result = detect_open_interest_anomaly(data[oi_col].dropna())
    oi_momentum = _safe_float(oi_result.get("oi_momentum"), 0.0)
    return _clip(oi_momentum / 100.0, -1.0, 1.0) * 0.0005, oi_result


def build_target_price_forecast(
    data: pd.DataFrame,
    current_price: float,
    close_col: str = "Close",
    volume_col: Optional[str] = "Volume",
    sentiment_data: Optional[Dict] = None,
    intervals: Iterable[Tuple[str, int]] = FORECAST_INTERVALS,
) -> Dict:
    """
    Forecast target prices for fixed intraday intervals.

    The blend intentionally stays explainable: recent price momentum, candle-pattern
    direction, volume confirmation, available open interest, news sentiment, and
    support/resistance gravity are combined into short-horizon target prices.
    """
    try:
        if data is None or data.empty or close_col not in data.columns:
            return {
                "rows": [],
                "confidence": 0.0,
                "signal": "WAIT",
                "message": "No market data available",
            }

        clean = data.copy().dropna(subset=[close_col])
        if clean.empty:
            return {
                "rows": [],
                "confidence": 0.0,
                "signal": "WAIT",
                "message": "No close-price data available",
            }

        current_price = _safe_float(current_price, _latest(clean[close_col]))
        pattern = detect_candlestick_patterns(clean, close_col)
        support_resistance = calculate_support_resistance(clean, close_col)

        if volume_col and volume_col in clean.columns:
            volume = detect_volume_anomaly(clean[volume_col].fillna(0), window=20)
        else:
            volume = {
                "is_anomaly": False,
                "anomaly_score": 0.0,
                "anomaly_type": "UNAVAILABLE",
                "volume_trend": "UNAVAILABLE",
            }

        oi_bias, oi_result = _open_interest_bias(clean)
        momentum = _momentum_bias(clean, close_col)
        pattern_component = _pattern_bias(
            pattern.get("signal", "HOLD"),
            _safe_float(pattern.get("confidence"), 0.0),
        )
        technical = _technical_bias(clean, close_col)
        sentiment = _sentiment_bias(sentiment_data)

        volume_score = _safe_float(volume.get("anomaly_score"), 0.0)
        volume_multiplier = 1.0 + min(volume_score, 100.0) / 350.0
        base_drift = (momentum + pattern_component + technical + sentiment + oi_bias) * volume_multiplier

        returns = clean[close_col].pct_change().replace([np.inf, -np.inf], np.nan).dropna()
        volatility = _safe_float(returns.tail(48).std(), 0.0)
        atr = _latest(clean.get("ATR", pd.Series(dtype=float)), current_price * volatility)
        atr_pct = (atr / current_price) if current_price > 0 else volatility
        interval_volatility = max(volatility, atr_pct / 14.0, 0.0001)

        support = _safe_float(support_resistance.get("support"), current_price * 0.995)
        resistance = _safe_float(support_resistance.get("resistance"), current_price * 1.005)
        confidence_seed = (
            _safe_float(pattern.get("confidence"), 0.0) * 0.35
            + min(volume_score, 100.0) * 0.20
            + _safe_float(sentiment_data.get("confidence"), 0.0) * 0.15 if sentiment_data else 10.0
        )
        confidence = _clip(confidence_seed + 35.0, 5.0, 95.0)

        rows = []
        for label, minutes in intervals:
            horizon_units = max(minutes / 15.0, 1.0)
            drift = base_drift * horizon_units
            volatility_cushion = interval_volatility * np.sqrt(horizon_units) * 0.25

            raw_target = current_price * (1.0 + drift)
            if raw_target >= current_price:
                expected_price = min(raw_target + current_price * volatility_cushion, resistance)
                direction = "UP"
            else:
                expected_price = max(raw_target - current_price * volatility_cushion, support)
                direction = "DOWN"

            expected_change_pct = (
                ((expected_price - current_price) / current_price) * 100.0
                if current_price
                else 0.0
            )

            rows.append(
                {
                    "Interval": label,
                    "Current Price": float(current_price),
                    "Forecast Expected Price": float(expected_price),
                    "Expected Change %": float(expected_change_pct),
                    "Direction": direction if abs(expected_change_pct) >= 0.01 else "FLAT",
                    "Confidence %": float(confidence),
                }
            )

        if base_drift > 0.0002:
            signal = "BULLISH"
        elif base_drift < -0.0002:
            signal = "BEARISH"
        else:
            signal = "NEUTRAL"

        return {
            "rows": rows,
            "confidence": float(confidence),
            "signal": signal,
            "base_drift": float(base_drift),
            "pattern": pattern,
            "support_resistance": support_resistance,
            "volume": volume,
            "open_interest": oi_result,
            "sentiment": sentiment_data or {},
        }

    except Exception as exc:
        return {
            "rows": [],
            "confidence": 0.0,
            "signal": "WAIT",
            "message": str(exc),
        }
