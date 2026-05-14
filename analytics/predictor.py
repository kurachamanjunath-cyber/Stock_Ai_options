"""ML-based options entry/target price predictor."""
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from typing import Dict, Tuple
import warnings
warnings.filterwarnings('ignore')

class OptionsPredictor:
    """ML predictor for options entry and target prices."""
    
    def __init__(self):
        self.scaler = StandardScaler()
        self.rf_model = None
        self.is_trained = False
    
    def prepare_features(self, data: pd.DataFrame, close_col: str = "Close") -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepare features for ML model.
        
        Args:
            data: Price data with technical indicators
            close_col: Column name for close price
        
        Returns:
            Features array and target array
        """
        
        required_features = [
            "RSI_14", "MACD", "MACD_Signal", "Volume_Trend",
            "SMA_10", "SMA_20", "BB_High", "BB_Low", "ATR"
        ]
        
        # Create additional features
        data_copy = data.copy()
        data_copy["Price_Change"] = data_copy[close_col].pct_change() * 100
        data_copy["Price_Momentum"] = data_copy[close_col].diff()
        data_copy["High_Low_Range"] = (data_copy["High"] - data_copy["Low"]) / data_copy[close_col] * 100
        
        available_features = [f for f in required_features if f in data_copy.columns]
        available_features.extend(["Price_Change", "Price_Momentum", "High_Low_Range"])
        available_features = list(set(available_features))
        
        X = data_copy[available_features].fillna(0)
        y = data_copy[close_col].values
        
        return X.values, y
    
    def train(self, data: pd.DataFrame, close_col: str = "Close") -> Dict:
        """
        Train ensemble model on historical data.
        
        Args:
            data: Historical price data
            close_col: Column name for close price
        
        Returns:
            Dict with training metrics
        """
        
        try:
            if len(data) < 50:
                return {
                    "status": "FAILED",
                    "message": "Insufficient data for training (need >= 50 samples)",
                    "samples": len(data)
                }
            
            X, y = self.prepare_features(data, close_col)
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )
            
            # Scale features
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Random Forest (primary model)
            self.rf_model = RandomForestRegressor(
                n_estimators=100,
                max_depth=15,
                random_state=42,
                n_jobs=-1
            )
            self.rf_model.fit(X_train_scaled, y_train)
            rf_score = self.rf_model.score(X_test_scaled, y_test)
            
            self.is_trained = True
            
            return {
                "status": "SUCCESS",
                "rf_score": float(rf_score),
                "training_samples": len(X_train),
                "test_samples": len(X_test)
            }
        
        except Exception as e:
            return {
                "status": "FAILED",
                "error": str(e)
            }
    
    def predict_next_prices(
        self,
        data: pd.DataFrame,
        days_ahead: int = 5,
        close_col: str = "Close"
    ) -> np.ndarray:
        """
        Predict prices for next N days.
        
        Args:
            data: Historical data with features
            days_ahead: Number of days to predict
            close_col: Close column name
        
        Returns:
            Array of predicted prices
        """
        
        if not self.is_trained:
            # Return simple extrapolation
            last_price = data[close_col].iloc[-1]
            return np.array([last_price] * days_ahead)
        
        try:
            X, _ = self.prepare_features(data, close_col)
            X_scaled = self.scaler.transform(X)
            
            # RandomForest predictions only (no XGBoost)
            rf_pred = self.rf_model.predict(X_scaled[-1:])
            
            # Simple momentum continuation
            prices = data[close_col].values
            momentum = prices[-1] - prices[-5] if len(prices) >= 5 else 0
            
            predictions = []
            current_pred = rf_pred[0]
            for _ in range(days_ahead):
                predictions.append(current_pred)
                current_pred += momentum / days_ahead
            
            return np.array(predictions)
        
        except Exception as e:
            last_price = data[close_col].iloc[-1]
            return np.array([last_price] * days_ahead)


def predict_options_entry_target(
    data: pd.DataFrame,
    current_price: float,
    days_ahead: int = 5,
    premium_pct_low: float = 0.02,
    premium_pct_high: float = 0.05,
    close_col: str = "Close"
) -> Dict:
    """
    Predict options entry and target prices.
    
    Args:
        data: Historical price data with indicators
        current_price: Current market price
        days_ahead: Forecast horizon
        premium_pct_low: Low range for option premium %
        premium_pct_high: High range for option premium %
        close_col: Close column name
    
    Returns:
        Dict with entry_price, target_price, stop_loss, signal, confidence
    """
    
    try:
        if len(data) < 30:
            return {
                "signal": "HOLD",
                "confidence": 0.0,
                "entry_price": current_price,
                "target_price": current_price,
                "stop_loss": current_price,
                "message": "Insufficient data"
            }
        
        # Initialize predictor
        predictor = OptionsPredictor()
        train_result = predictor.train(data, close_col)
        
        if train_result["status"] != "SUCCESS":
            return {
                "signal": "HOLD",
                "confidence": 0.0,
                "entry_price": current_price,
                "target_price": current_price,
                "stop_loss": current_price,
                "error": train_result.get("message", "Training failed")
            }
        
        # Get predictions
        predictions = predictor.predict_next_prices(data, days_ahead, close_col)
        avg_pred = np.mean(predictions)
        max_pred = np.max(predictions)
        min_pred = np.min(predictions)
        
        # Determine signal and prices
        bullish_threshold = 1.02
        bearish_threshold = 0.98
        
        direction_ratio = avg_pred / current_price
        
        if direction_ratio > bullish_threshold:
            # CALL signal
            signal = "BUY_CALL"
            entry_price = current_price * (1 + np.random.uniform(premium_pct_low, premium_pct_high))
            target_price = max_pred * 0.95  # Take 95% of upside
            stop_loss = min_pred * 0.90  # Exit if falls 10%
            
        elif direction_ratio < bearish_threshold:
            # PUT signal
            signal = "BUY_PUT"
            entry_price = current_price * (1 + np.random.uniform(premium_pct_low, premium_pct_high))
            target_price = min_pred * 1.05  # Take 95% of downside
            stop_loss = max_pred * 1.10  # Exit if rises 10%
        else:
            # HOLD
            signal = "HOLD"
            entry_price = current_price
            target_price = current_price
            stop_loss = current_price
        
        # Calculate confidence (0-100)
        # Based on prediction strength and consistency
        pred_strength = abs(direction_ratio - 1) * 100
        pred_consistency = 100 - (np.std(predictions) / current_price * 100)
        confidence = np.mean([pred_strength, pred_consistency])
        confidence = min(100, max(0, confidence))
        
        # Risk-Reward Ratio
        if signal != "HOLD":
            if signal == "BUY_CALL":
                profit = target_price - entry_price
                loss = entry_price - stop_loss
            else:  # BUY_PUT
                profit = entry_price - target_price
                loss = stop_loss - entry_price
            
            risk_reward = profit / loss if loss > 0 else 0
        else:
            risk_reward = 0
        
        return {
            "signal": signal,
            "confidence": float(confidence),
            "entry_price": float(entry_price),
            "target_price": float(target_price),
            "stop_loss": float(stop_loss),
            "risk_reward_ratio": float(risk_reward),
            "predicted_price": float(avg_pred),
            "max_price": float(max_pred),
            "min_price": float(min_pred),
            "model_scores": {
                "rf_score": train_result.get("rf_score", 0),
                "xgb_score": train_result.get("xgb_score", 0)
            }
        }
    
    except Exception as e:
        return {
            "signal": "HOLD",
            "confidence": 0.0,
            "entry_price": current_price,
            "target_price": current_price,
            "stop_loss": current_price,
            "error": str(e)
        }


def calculate_multi_factor_score(
    price_trend_signal: str,
    technical_signal: str,
    volume_score: float,
    sentiment_score: float,
    greeks_signal: str,
    weights: Dict = None
) -> Dict:
    """
    Calculate weighted multi-factor confidence score.
    
    Args:
        price_trend_signal: 'BULLISH', 'BEARISH', 'NEUTRAL'
        technical_signal: 'BULLISH', 'BEARISH', 'NEUTRAL'
        volume_score: 0-100 (volume anomaly strength)
        sentiment_score: -1 to +1 (overall sentiment)
        greeks_signal: 'BULLISH', 'BEARISH', 'NEUTRAL'
        weights: Dict of weights for each factor (default equal)
    
    Returns:
        Dict with overall_score (0-100), bullish_score, bearish_score, factors
    """
    
    if weights is None:
        weights = {
            "price_trend": 0.25,
            "technical": 0.25,
            "volume": 0.15,
            "sentiment": 0.20,
            "greeks": 0.15
        }
    
    # Convert signals to numeric scores (0-100)
    price_score = 75 if price_trend_signal == "BULLISH" else 25 if price_trend_signal == "BEARISH" else 50
    technical_score = 75 if technical_signal == "BULLISH" else 25 if technical_signal == "BEARISH" else 50
    volume_score = volume_score  # Already 0-100
    sentiment_score_num = (sentiment_score + 1) * 50  # -1 to +1 → 0 to 100
    greeks_score = 75 if greeks_signal == "BULLISH" else 25 if greeks_signal == "BEARISH" else 50
    
    # Calculate weighted score
    overall_score = (
        price_score * weights["price_trend"] +
        technical_score * weights["technical"] +
        volume_score * weights["volume"] +
        sentiment_score_num * weights["sentiment"] +
        greeks_score * weights["greeks"]
    )
    
    # Determine bullish vs bearish
    bullish_score = overall_score if overall_score > 50 else max(0, 50 - overall_score)
    bearish_score = (100 - overall_score) if overall_score < 50 else max(0, overall_score - 50)
    
    return {
        "overall_score": float(overall_score),
        "bullish_score": float(bullish_score),
        "bearish_score": float(bearish_score),
        "factors": {
            "price_trend": float(price_score),
            "technical": float(technical_score),
            "volume": float(volume_score),
            "sentiment": float(sentiment_score_num),
            "greeks": float(greeks_score)
        },
        "signal": "STRONG_BUY" if overall_score > 75 else "BUY" if overall_score > 60 else "HOLD" if overall_score > 40 else "SELL" if overall_score > 25 else "STRONG_SELL"
    }
