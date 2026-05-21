"""Intraday options recommendations based on candlestick patterns and support/resistance."""
import pandas as pd
import numpy as np
from typing import Dict
from .candlestick_patterns import detect_candlestick_patterns, calculate_support_resistance

def recommend_intraday_options(
    data: pd.DataFrame,
    current_price: float,
    strike_interval: int = 100,
    close_col: str = "Close"
) -> Dict:
    """
    Recommend specific options (strike, call/put) for intraday trading based on patterns AND technicals.
    
    Args:
        data: OHLCV data with intraday candles
        current_price: Current market price
        strike_interval: Round to nearest interval
        close_col: Close column name
    
    Returns:
        Dict with recommended call/put strikes and entry prices for today
    """
    try:
        if len(data) < 5:
            return {
                "signal": "INSUFFICIENT_DATA",
                "message": "Need at least 5 candles for pattern analysis",
                "today_recommendation": None
            }
        
        # Detect candlestick patterns
        pattern_analysis = detect_candlestick_patterns(data, close_col)
        
        # Calculate support/resistance
        support_resistance = calculate_support_resistance(data, close_col)
        
        current_high = data["High"].iloc[-1]
        current_low = data["Low"].iloc[-1]
        
        support = support_resistance.get("support", current_low)
        resistance = support_resistance.get("resistance", current_high)
        pivot = support_resistance.get("pivot", current_price)
        
        # Calculate technical indicators
        closes = data[close_col].values
        rsi = _calculate_rsi(closes, period=14)
        sma_10 = closes[-10:].mean() if len(closes) >= 10 else closes.mean()
        sma_20 = closes[-20:].mean() if len(closes) >= 20 else closes.mean()
        
        # Determine technical bias
        price_above_sma20 = current_price > sma_20
        rsi_bullish = rsi < 70 and rsi > 30
        rsi_bearish = rsi > 30 and rsi < 70
        
        # Recommend strikes
        recommendation = {
            "pattern": pattern_analysis["current_pattern"],
            "pattern_confidence": pattern_analysis["confidence"],
            "pattern_signal": pattern_analysis["signal"],
            "trend": pattern_analysis.get("trend", "UNKNOWN"),
            "current_price": float(current_price),
            "support": float(support),
            "resistance": float(resistance),
            "pivot": float(pivot),
            "rsi": float(rsi),
            "sma_10": float(sma_10),
            "sma_20": float(sma_20),
            "today_trades": []
        }
        
        signal = pattern_analysis["signal"]
        
        # ===== SIGNAL VALIDATION WITH TECHNICAL CONFIRMATION =====
        
        # Only give BUY_CALL if:
        # 1. Pattern suggests bullish AND
        # 2. Price is above SMA20 (in uptrend) AND
        # 3. RSI is not overbought
        if signal == "BUY_CALL":
            if price_above_sma20 and rsi < 70:
                # Strong bullish setup
                confidence = pattern_analysis["confidence"]
                
                # Find nearest ATM strike
                atm_strike = round(current_price / strike_interval) * strike_interval
                
                # Primary: ATM Call
                call_entry_price = current_price * 0.02  # Premium is typically 1-2% of strike
                
                recommendation["today_trades"].append({
                    "type": "CALL",
                    "strike": float(atm_strike),
                    "entry_price": float(call_entry_price),
                    "target_price": float(resistance),
                    "stop_loss": float(support),
                    "confidence": confidence,
                    "pattern": pattern_analysis["current_pattern"],
                    "priority": "PRIMARY",
                    "upside_potential": float(((resistance - current_price) / current_price) * 100),
                    "technical_confirmation": f"Price above SMA20, RSI={rsi:.1f}"
                })
                
                # Secondary: OTM Call (higher risk, higher reward)
                otm_strike = atm_strike + strike_interval
                otm_entry = (call_entry_price * 0.6)  # OTM is cheaper
                
                recommendation["today_trades"].append({
                    "type": "CALL",
                    "strike": float(otm_strike),
                    "entry_price": float(otm_entry),
                    "target_price": float(resistance),
                    "stop_loss": float(support),
                    "confidence": confidence * 0.8,
                    "pattern": pattern_analysis["current_pattern"],
                    "priority": "SECONDARY",
                    "upside_potential": float(((resistance - current_price) / current_price) * 100),
                    "technical_confirmation": "Higher risk, higher reward"
                })
                
                recommendation["signal"] = "BUY_CALL"
                recommendation["overall_direction"] = "BULLISH"
            else:
                # Weak bullish signal - convert to WAIT
                recommendation["signal"] = "WAIT"
                recommendation["overall_direction"] = "NEUTRAL"
                reason = []
                if not price_above_sma20:
                    reason.append("Price below SMA20")
                if rsi >= 70:
                    reason.append("RSI overbought")
                recommendation["message"] = f"Pattern suggests CALL but: {', '.join(reason)}"
        
        # Only give BUY_PUT if:
        # 1. Pattern suggests bearish AND
        # 2. Price is below SMA20 (in downtrend) AND
        # 3. RSI is not oversold
        elif signal == "BUY_PUT":
            if not price_above_sma20 and rsi > 30:
                # Strong bearish setup
                confidence = pattern_analysis["confidence"]
                
                # Find nearest ATM strike
                atm_strike = round(current_price / strike_interval) * strike_interval
                
                # Primary: ATM Put
                put_entry_price = current_price * 0.02  # Premium
                
                recommendation["today_trades"].append({
                    "type": "PUT",
                    "strike": float(atm_strike),
                    "entry_price": float(put_entry_price),
                    "target_price": float(support),
                    "stop_loss": float(resistance),
                    "confidence": confidence,
                    "pattern": pattern_analysis["current_pattern"],
                    "priority": "PRIMARY",
                    "downside_potential": float(((current_price - support) / current_price) * 100),
                    "technical_confirmation": f"Price below SMA20, RSI={rsi:.1f}"
                })
                
                # Secondary: OTM Put
                otm_strike = atm_strike - strike_interval if atm_strike > strike_interval else atm_strike
                otm_entry = (put_entry_price * 0.6)  # OTM is cheaper
                
                recommendation["today_trades"].append({
                    "type": "PUT",
                    "strike": float(otm_strike),
                    "entry_price": float(otm_entry),
                    "target_price": float(support),
                    "stop_loss": float(resistance),
                    "confidence": confidence * 0.8,
                    "pattern": pattern_analysis["current_pattern"],
                    "priority": "SECONDARY",
                    "downside_potential": float(((current_price - support) / current_price) * 100),
                    "technical_confirmation": "Higher risk, higher reward"
                })
                
                recommendation["signal"] = "BUY_PUT"
                recommendation["overall_direction"] = "BEARISH"
            else:
                # Weak bearish signal - convert to WAIT
                recommendation["signal"] = "WAIT"
                recommendation["overall_direction"] = "NEUTRAL"
                reason = []
                if price_above_sma20:
                    reason.append("Price above SMA20")
                if rsi <= 30:
                    reason.append("RSI oversold")
                recommendation["message"] = f"Pattern suggests PUT but: {', '.join(reason)}"
        
        # ===== NEUTRAL/WAIT =====
        else:
            recommendation["signal"] = "WAIT"
            recommendation["overall_direction"] = "NEUTRAL"
            recommendation["message"] = "No clear pattern or technical confirmation. Consider waiting for better setup."
        
        return recommendation
    
    except Exception as e:
        return {
            "signal": "ERROR",
            "error": str(e),
            "today_trades": [],
            "today_recommendation": None
        }


def _calculate_rsi(prices: np.ndarray, period: int = 14) -> float:
    """Calculate RSI for the latest candle."""
    if len(prices) < period + 1:
        return 50.0
    
    deltas = np.diff(prices[-period-1:])
    seed = deltas[:period]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    rs = up / down if down != 0 else 0
    rsi = 100.0 - 100.0 / (1.0 + rs)
    
    for delta in deltas[period:]:
        if delta > 0:
            up = (up * (period - 1) + delta) / period
            down = down * (period - 1) / period
        else:
            down = (down * (period - 1) - delta) / period
            up = up * (period - 1) / period
        
        rs = up / down if down != 0 else 0
        rsi = 100.0 - 100.0 / (1.0 + rs)
    
    return rsi


def get_intraday_price_targets(current_price: float, pattern_signal: str, volatility: float = 0.02) -> Dict:
    """
    Calculate intraday price targets based on current price and volatility.
    
    Args:
        current_price: Current market price
        pattern_signal: Signal from candlestick pattern (BUY_CALL/BUY_PUT/WAIT)
        volatility: Expected volatility as percentage (default 2%)
    
    Returns:
        Dict with intraday targets
    """
    
    day_move = current_price * volatility
    
    targets = {
        "very_bullish": current_price + (day_move * 2),
        "bullish": current_price + day_move,
        "current": current_price,
        "bearish": current_price - day_move,
        "very_bearish": current_price - (day_move * 2),
    }
    
    if pattern_signal == "BUY_CALL":
        targets["expected_target"] = targets["bullish"]
        targets["breakeven"] = current_price
        targets["risk_zone"] = targets["bearish"]
    elif pattern_signal == "BUY_PUT":
        targets["expected_target"] = targets["bearish"]
        targets["breakeven"] = current_price
        targets["risk_zone"] = targets["bullish"]
    else:
        targets["expected_target"] = targets["current"]
    
    return targets
