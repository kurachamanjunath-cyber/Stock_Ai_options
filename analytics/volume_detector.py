"""Volume anomaly detection for trading opportunities."""
import numpy as np
import pandas as pd
from typing import Dict, Tuple

def detect_volume_anomaly(
    volume_data: pd.Series,
    window: int = 20,
    threshold_sigma: float = 2.0
) -> Dict:
    """
    Detect volume anomalies using rolling statistics.
    
    Args:
        volume_data: Series of volume data
        window: Rolling window size for mean/std calculation
        threshold_sigma: Number of standard deviations for threshold
    
    Returns:
        Dict with is_anomaly, anomaly_score, details
    """
    
    try:
        if len(volume_data) < window:
            return {
                "is_anomaly": False,
                "anomaly_score": 0.0,
                "message": "Insufficient data",
                "current_volume": float(volume_data.iloc[-1]),
                "avg_volume": 0.0
            }
        
        # Calculate rolling statistics
        rolling_mean = volume_data.rolling(window=window).mean()
        rolling_std = volume_data.rolling(window=window).std()
        
        current_volume = float(volume_data.iloc[-1])
        avg_volume = float(rolling_mean.iloc[-1])
        volume_std = float(rolling_std.iloc[-1])
        
        # Calculate z-score
        if volume_std > 0:
            z_score = (current_volume - avg_volume) / volume_std
        else:
            z_score = 0.0
        
        # Determine if anomaly
        is_anomaly = z_score > threshold_sigma
        
        # Anomaly score: 0-100
        anomaly_score = min(100, abs(z_score) / threshold_sigma * 100)
        
        # Classify anomaly type
        if current_volume > avg_volume:
            anomaly_type = "HIGH_VOLUME" if is_anomaly else "ABOVE_AVERAGE"
        else:
            anomaly_type = "LOW_VOLUME" if is_anomaly else "BELOW_AVERAGE"
        
        # Recent volume trend (last 5 days)
        recent_volumes = volume_data.tail(5)
        volume_trend = "INCREASING" if recent_volumes.iloc[-1] > recent_volumes.iloc[0] else "DECREASING"
        
        return {
            "is_anomaly": bool(is_anomaly),
            "anomaly_score": float(anomaly_score),
            "z_score": float(z_score),
            "current_volume": current_volume,
            "avg_volume": avg_volume,
            "volume_std": volume_std,
            "anomaly_type": anomaly_type,
            "volume_trend": volume_trend,
            "ratio_to_avg": float(current_volume / avg_volume) if avg_volume > 0 else 1.0
        }
    
    except Exception as e:
        return {
            "is_anomaly": False,
            "anomaly_score": 0.0,
            "error": str(e),
            "current_volume": 0.0,
            "avg_volume": 0.0
        }


def detect_put_call_ratio_anomaly(
    put_volume: float,
    call_volume: float,
    threshold_high: float = 1.5,
    threshold_low: float = 0.7
) -> Dict:
    """
    Detect Put/Call ratio extremes.
    
    Args:
        put_volume: Put option volume
        call_volume: Call option volume
        threshold_high: High PCR threshold (bearish)
        threshold_low: Low PCR threshold (bullish)
    
    Returns:
        Dict with PCR value, signal, extremeness
    """
    
    try:
        if call_volume <= 0:
            return {
                "pcr": 0.0,
                "signal": "UNKNOWN",
                "is_extreme": False,
                "extremeness": 0.0
            }
        
        pcr = put_volume / call_volume
        
        if pcr > threshold_high:
            signal = "BEARISH_EXTREME"
            extremeness = min(100, (pcr - threshold_high) / threshold_high * 100)
        elif pcr < threshold_low:
            signal = "BULLISH_EXTREME"
            extremeness = min(100, (threshold_low - pcr) / threshold_low * 100)
        else:
            signal = "NEUTRAL"
            extremeness = 0.0
        
        return {
            "pcr": float(pcr),
            "put_volume": float(put_volume),
            "call_volume": float(call_volume),
            "signal": signal,
            "is_extreme": extremeness > 50,
            "extremeness": float(extremeness)
        }
    
    except Exception as e:
        return {
            "pcr": 0.0,
            "signal": "ERROR",
            "is_extreme": False,
            "extremeness": 0.0,
            "error": str(e)
        }


def detect_open_interest_anomaly(
    oi_data: pd.Series,
    window: int = 10
) -> Dict:
    """
    Detect unusual open interest changes.
    
    Args:
        oi_data: Series of open interest data
        window: Window for trend calculation
    
    Returns:
        Dict with OI trend and strength
    """
    
    try:
        if len(oi_data) < 2:
            return {
                "oi_trend": "UNKNOWN",
                "oi_change_pct": 0.0,
                "oi_momentum": 0.0
            }
        
        current_oi = oi_data.iloc[-1]
        prev_oi = oi_data.iloc[-2]
        oi_change_pct = ((current_oi - prev_oi) / prev_oi * 100) if prev_oi > 0 else 0.0
        
        # Trend over window
        if len(oi_data) >= window:
            window_avg = oi_data.tail(window).mean()
            oi_momentum = ((current_oi - window_avg) / window_avg * 100) if window_avg > 0 else 0.0
        else:
            oi_momentum = oi_change_pct
        
        if oi_change_pct > 5:
            trend = "INCREASING"
        elif oi_change_pct < -5:
            trend = "DECREASING"
        else:
            trend = "STABLE"
        
        return {
            "oi_trend": trend,
            "oi_change_pct": float(oi_change_pct),
            "oi_momentum": float(oi_momentum),
            "current_oi": float(current_oi),
            "previous_oi": float(prev_oi)
        }
    
    except Exception as e:
        return {
            "oi_trend": "ERROR",
            "oi_change_pct": 0.0,
            "oi_momentum": 0.0,
            "error": str(e)
        }
