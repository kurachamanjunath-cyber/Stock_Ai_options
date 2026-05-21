"""Candlestick pattern detection for intraday trading strategy."""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple

def detect_candlestick_patterns(data: pd.DataFrame, close_col: str = "Close") -> Dict:
    """
    Detect major candlestick patterns used by professional traders.
    
    Args:
        data: OHLCV data with at least last 5 candles
        close_col: Column name for close price
    
    Returns:
        Dict with detected patterns and confidence scores
    """
    try:
        if len(data) < 5:
            return {
                "patterns": [],
                "current_pattern": "INSUFFICIENT_DATA",
                "confidence": 0,
                "signal": "HOLD"
            }
        
        # Get last candles
        o = data["Open"].values
        h = data["High"].values
        l = data["Low"].values
        c = data[close_col].values
        v = data["Volume"].values if "Volume" in data.columns else np.ones(len(data))
        
        patterns = []
        current_pattern = None
        confidence = 0
        signal = "NEUTRAL"
        pattern_direction = None
        
        # Calculate trend using simple moving averages
        sma_10 = c[-10:].mean() if len(c) >= 10 else c.mean()
        sma_20 = c[-20:].mean() if len(c) >= 20 else c.mean()
        current_price = c[-1]
        
        # Determine overall trend
        trend = "BULLISH" if sma_10 > sma_20 else "BEARISH" if sma_10 < sma_20 else "NEUTRAL"
        
        # ===== SINGLE CANDLE PATTERNS =====
        
        # Hammer (Bullish reversal - only valid in downtrend)
        if is_hammer(o[-1], h[-1], l[-1], c[-1]):
            patterns.append(("HAMMER", "BULLISH_SIGNAL", 75))
            pattern_direction = "BULLISH"
            if trend != "BEARISH":  # Only trust hammer in downtrend or early recovery
                current_pattern = "HAMMER"
                confidence = 60
                signal = "BUY_CALL"
        
        # Inverted Hammer (Bearish reversal - only valid in uptrend)
        elif is_inverted_hammer(o[-1], h[-1], l[-1], c[-1]):
            patterns.append(("INVERTED_HAMMER", "BEARISH_SIGNAL", 70))
            pattern_direction = "BEARISH"
            if trend != "BULLISH":  # Only trust in uptrend or early reversal
                current_pattern = "INVERTED_HAMMER"
                confidence = 60
                signal = "BUY_PUT"
        
        # Doji (Indecision)
        elif is_doji(o[-1], h[-1], l[-1], c[-1]):
            patterns.append(("DOJI", "NEUTRAL", 60))
            current_pattern = "DOJI"
            confidence = 50
            signal = "WAIT"
        
        # Spinning Top (Indecision)
        elif is_spinning_top(o[-1], h[-1], l[-1], c[-1]):
            patterns.append(("SPINNING_TOP", "NEUTRAL", 50))
            current_pattern = "SPINNING_TOP"
            confidence = 45
            signal = "WAIT"
        
        # Marubozu (Strong bullish/bearish) - ONLY IN TREND DIRECTION
        elif is_marubozu_bullish(o[-1], h[-1], l[-1], c[-1]):
            patterns.append(("MARUBOZU_BULLISH", "BULLISH_SIGNAL", 85))
            pattern_direction = "BULLISH"
            if trend == "BULLISH":  # Confirm with trend
                current_pattern = "MARUBOZU_BULLISH"
                confidence = 85
                signal = "BUY_CALL"
            else:
                current_pattern = "MARUBOZU_BULLISH"
                confidence = 50
                signal = "WAIT"
        
        elif is_marubozu_bearish(o[-1], h[-1], l[-1], c[-1]):
            patterns.append(("MARUBOZU_BEARISH", "BEARISH_SIGNAL", 85))
            pattern_direction = "BEARISH"
            if trend == "BEARISH":  # Confirm with trend
                current_pattern = "MARUBOZU_BEARISH"
                confidence = 85
                signal = "BUY_PUT"
            else:
                current_pattern = "MARUBOZU_BEARISH"
                confidence = 50
                signal = "WAIT"
        
        # ===== TWO CANDLE PATTERNS =====
        
        if len(data) >= 2:
            # Engulfing Pattern (Strong reversal)
            engulf_result = is_engulfing(o[-2], c[-2], o[-1], h[-1], l[-1], c[-1])
            if engulf_result:
                pattern_name, direction, conf = engulf_result
                patterns.append((pattern_name, direction, conf))
                if not current_pattern:
                    # Bullish engulfing only valid if price below SMA or in recovery
                    if direction == "BULLISH" and current_price > sma_20:
                        current_pattern = pattern_name
                        confidence = conf
                        signal = "BUY_CALL"
                    # Bearish engulfing only valid if price above SMA or in decline
                    elif direction == "BEARISH" and current_price < sma_20:
                        current_pattern = pattern_name
                        confidence = conf
                        signal = "BUY_PUT"
            
            # Harami Pattern (Reversal)
            harami_result = is_harami(o[-2], c[-2], o[-1], h[-1], l[-1], c[-1])
            if harami_result:
                pattern_name, direction, conf = harami_result
                patterns.append((pattern_name, direction, conf))
        
        # ===== THREE CANDLE PATTERNS =====
        
        if len(data) >= 3:
            # Morning Star (Bullish reversal - at bottoms)
            if is_morning_star(o, h, l, c):
                patterns.append(("MORNING_STAR", "BULLISH", 80))
                if not current_pattern and current_price > sma_20:
                    current_pattern = "MORNING_STAR"
                    confidence = 80
                    signal = "BUY_CALL"
            
            # Evening Star (Bearish reversal - at tops)
            elif is_evening_star(o, h, l, c):
                patterns.append(("EVENING_STAR", "BEARISH", 80))
                if not current_pattern and current_price < sma_20:
                    current_pattern = "EVENING_STAR"
                    confidence = 80
                    signal = "BUY_PUT"
        
        # ===== TREND PATTERNS =====
        
        if len(data) >= 5:
            # Higher Highs & Higher Lows (Uptrend)
            if is_higher_highs_lows(h, l):
                patterns.append(("HIGHER_HIGHS_LOWS", "BULLISH", 70))
                if not current_pattern:
                    current_pattern = "HIGHER_HIGHS_LOWS"
                    confidence = 75
                    signal = "BUY_CALL"
            
            # Lower Highs & Lower Lows (Downtrend)
            elif is_lower_highs_lows(h, l):
                patterns.append(("LOWER_HIGHS_LOWS", "BEARISH", 70))
                if not current_pattern:
                    current_pattern = "LOWER_HIGHS_LOWS"
                    confidence = 75
                    signal = "BUY_PUT"
        
        # If still no clear signal, use trend as fallback
        if signal == "NEUTRAL" and not current_pattern:
            if trend == "BULLISH":
                current_pattern = "TREND_FOLLOWING"
                confidence = 65
                signal = "BUY_CALL"
            elif trend == "BEARISH":
                current_pattern = "TREND_FOLLOWING"
                confidence = 65
                signal = "BUY_PUT"
            else:
                current_pattern = "NO_PATTERN"
                confidence = 0
                signal = "WAIT"
        
        return {
            "patterns": patterns,
            "current_pattern": current_pattern or "NO_PATTERN",
            "confidence": confidence,
            "signal": signal,
            "trend": trend,
            "current_close": float(c[-1]),
            "current_high": float(h[-1]),
            "current_low": float(l[-1])
        }
    
    except Exception as e:
        return {
            "patterns": [],
            "current_pattern": "ERROR",
            "confidence": 0,
            "signal": "HOLD",
            "trend": "UNKNOWN",
            "error": str(e)
        }

# ===== SINGLE CANDLE DETECTORS =====

def is_hammer(o: float, h: float, l: float, c: float) -> bool:
    """Hammer: Small body at top, long lower wick. Bullish reversal."""
    body_size = abs(c - o)
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l
    
    return lower_wick > 2 * body_size and upper_wick < body_size * 0.5 and body_size > 0

def is_inverted_hammer(o: float, h: float, l: float, c: float) -> bool:
    """Inverted Hammer: Small body at bottom, long upper wick. Bearish."""
    body_size = abs(c - o)
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l
    
    return upper_wick > 2 * body_size and lower_wick < body_size * 0.5 and body_size > 0

def is_doji(o: float, h: float, l: float, c: float) -> bool:
    """Doji: Open ≈ Close, long wicks both sides. Indecision."""
    body_size = abs(c - o)
    total_range = h - l
    
    return body_size < total_range * 0.05 and total_range > 0

def is_spinning_top(o: float, h: float, l: float, c: float) -> bool:
    """Spinning Top: Small body in middle, moderate wicks. Indecision."""
    body_size = abs(c - o)
    total_range = h - l
    
    return body_size < total_range * 0.3 and total_range > 0 and body_size > total_range * 0.1

def is_marubozu_bullish(o: float, h: float, l: float, c: float) -> bool:
    """Marubozu Bullish: Open = Low, Close = High. Strong bullish."""
    return abs(o - l) < (h - l) * 0.02 and abs(c - h) < (h - l) * 0.02 and c > o

def is_marubozu_bearish(o: float, h: float, l: float, c: float) -> bool:
    """Marubozu Bearish: Open = High, Close = Low. Strong bearish."""
    return abs(o - h) < (h - l) * 0.02 and abs(c - l) < (h - l) * 0.02 and c < o

# ===== TWO CANDLE DETECTORS =====

def is_engulfing(o1: float, c1: float, o2: float, h2: float, l2: float, c2: float) -> Tuple or None:
    """Engulfing: Second candle's body completely engulfs first candle's body."""
    body1_open = min(o1, c1)
    body1_close = max(o1, c1)
    body2_open = min(o2, c2)
    body2_close = max(o2, c2)
    
    # Bullish engulfing
    if c2 > o2 and body2_open < body1_open and body2_close > body1_close:
        return ("BULLISH_ENGULFING", "BULLISH", 85)
    
    # Bearish engulfing
    if c2 < o2 and body2_open > body1_close and body2_close < body1_open:
        return ("BEARISH_ENGULFING", "BEARISH", 85)
    
    return None

def is_harami(o1: float, c1: float, o2: float, h2: float, l2: float, c2: float) -> Tuple or None:
    """Harami: Second candle's body is inside first candle's body. Reversal."""
    body1_open = min(o1, c1)
    body1_close = max(o1, c1)
    body2_open = min(o2, c2)
    body2_close = max(o2, c2)
    
    # Bodies must not overlap significantly
    if body2_open > body1_open and body2_close < body1_close:
        if c2 > o2:  # Bullish harami
            return ("BULLISH_HARAMI", "BULLISH", 70)
        else:  # Bearish harami
            return ("BEARISH_HARAMI", "BEARISH", 70)
    
    return None

# ===== THREE CANDLE DETECTORS =====

def is_morning_star(o: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray) -> bool:
    """Morning Star: Long bearish, small body, then long bullish. Bullish reversal."""
    if len(c) < 3:
        return False
    
    # First candle: bearish
    if c[-3] > o[-3]:
        return False
    
    # Second candle: small body (gap down)
    body2_size = abs(c[-2] - o[-2])
    candle1_size = abs(c[-3] - o[-3])
    
    if body2_size > candle1_size * 0.5:
        return False
    
    # Third candle: bullish, closes above first candle's midpoint
    if c[-1] < o[-1]:
        return False
    
    midpoint = (c[-3] + o[-3]) / 2
    return c[-1] > midpoint

def is_evening_star(o: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray) -> bool:
    """Evening Star: Long bullish, small body, then long bearish. Bearish reversal."""
    if len(c) < 3:
        return False
    
    # First candle: bullish
    if c[-3] < o[-3]:
        return False
    
    # Second candle: small body (gap up)
    body2_size = abs(c[-2] - o[-2])
    candle1_size = abs(c[-3] - o[-3])
    
    if body2_size > candle1_size * 0.5:
        return False
    
    # Third candle: bearish, closes below first candle's midpoint
    if c[-1] > o[-1]:
        return False
    
    midpoint = (c[-3] + o[-3]) / 2
    return c[-1] < midpoint

# ===== TREND DETECTORS =====

def is_higher_highs_lows(h: np.ndarray, l: np.ndarray) -> bool:
    """Higher Highs & Higher Lows: Strong uptrend pattern."""
    if len(h) < 5:
        return False
    
    # Check last 5 candles for higher highs and higher lows
    higher_highs = h[-1] > h[-2] > h[-3] and h[-2] > h[-4]
    higher_lows = l[-1] > l[-2] > l[-3] and l[-2] > l[-4]
    
    return higher_highs and higher_lows

def is_lower_highs_lows(h: np.ndarray, l: np.ndarray) -> bool:
    """Lower Highs & Lower Lows: Strong downtrend pattern."""
    if len(h) < 5:
        return False
    
    # Check last 5 candles for lower highs and lower lows
    lower_highs = h[-1] < h[-2] < h[-3] and h[-2] < h[-4]
    lower_lows = l[-1] < l[-2] < l[-3] and l[-2] < l[-4]
    
    return lower_highs and lower_lows

def calculate_support_resistance(data: pd.DataFrame, close_col: str = "Close", window: int = 20) -> Dict:
    """
    Calculate support and resistance levels.
    
    Args:
        data: OHLCV data
        close_col: Close column name
        window: Lookback period
    
    Returns:
        Dict with support/resistance levels
    """
    try:
        if len(data) < window:
            return {
                "support": float(data["Low"].min()),
                "resistance": float(data["High"].max()),
                "pivot": float(data[close_col].iloc[-1])
            }
        
        recent_data = data.tail(window)
        
        # Pivot Point calculation
        high = recent_data["High"].max()
        low = recent_data["Low"].min()
        close = recent_data[close_col].iloc[-1]
        
        pivot = (high + low + close) / 3
        resistance = (2 * pivot) - low
        support = (2 * pivot) - high
        
        return {
            "support": float(support),
            "resistance": float(resistance),
            "pivot": float(pivot),
            "level_high": float(high),
            "level_low": float(low)
        }
    
    except Exception as e:
        return {
            "support": 0,
            "resistance": 0,
            "pivot": 0,
            "error": str(e)
        }
