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
    Recommend specific options (strike, call/put) for intraday trading based on patterns.
    
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
        
        # Recommend strikes
        recommendation = {
            "pattern": pattern_analysis["current_pattern"],
            "pattern_confidence": pattern_analysis["confidence"],
            "current_price": float(current_price),
            "support": float(support),
            "resistance": float(resistance),
            "pivot": float(pivot),
            "today_trades": []
        }
        
        signal = pattern_analysis["signal"]
        
        # ===== BUY CALL RECOMMENDATION =====
        if signal == "BUY_CALL":
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
                "confidence": pattern_analysis["confidence"],
                "pattern": pattern_analysis["current_pattern"],
                "priority": "PRIMARY",
                "upside_potential": float(((resistance - current_price) / current_price) * 100)
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
                "confidence": pattern_analysis["confidence"] * 0.8,
                "pattern": pattern_analysis["current_pattern"],
                "priority": "SECONDARY",
                "upside_potential": float(((resistance - current_price) / current_price) * 100)
            })
            
            recommendation["signal"] = "BUY_CALL"
            recommendation["overall_direction"] = "BULLISH"
        
        # ===== BUY PUT RECOMMENDATION =====
        elif signal == "BUY_PUT":
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
                "confidence": pattern_analysis["confidence"],
                "pattern": pattern_analysis["current_pattern"],
                "priority": "PRIMARY",
                "downside_potential": float(((current_price - support) / current_price) * 100)
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
                "confidence": pattern_analysis["confidence"] * 0.8,
                "pattern": pattern_analysis["current_pattern"],
                "priority": "SECONDARY",
                "downside_potential": float(((current_price - support) / current_price) * 100)
            })
            
            recommendation["signal"] = "BUY_PUT"
            recommendation["overall_direction"] = "BEARISH"
        
        # ===== NEUTRAL/WAIT =====
        else:
            recommendation["signal"] = "WAIT"
            recommendation["overall_direction"] = "NEUTRAL"
            recommendation["message"] = "No clear pattern detected. Consider waiting for better setup."
        
        return recommendation
    
    except Exception as e:
        return {
            "signal": "ERROR",
            "error": str(e),
            "today_trades": [],
            "today_recommendation": None
        }

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
