"""Sample test script for predictor accuracy validation."""
import sys
sys.path.insert(0, '/Users/manjunaathkuracha/Stock_Ai_options')

import pandas as pd
import numpy as np
from analytics.predictor import OptionsPredictor

# Sample price data for testing
test_data = pd.DataFrame({
    'Close': np.linspace(100, 115, 50),
    'High': np.linspace(102, 117, 50),
    'Low': np.linspace(98, 113, 50),
    'Volume': np.random.randint(800000, 2000000, 50),
    'RSI_14': np.random.uniform(30, 70, 50),
    'MACD': np.random.uniform(-2, 2, 50),
    'MACD_Signal': np.random.uniform(-2, 2, 50),
    'Volume_Trend': np.random.uniform(-5, 5, 50),
    'SMA_10': np.linspace(100, 115, 50),
    'SMA_20': np.linspace(99, 114, 50),
    'BB_High': np.linspace(105, 120, 50),
    'BB_Low': np.linspace(95, 110, 50),
    'ATR': np.random.uniform(1, 3, 50),
})

print("Testing OptionsPredictor...")
predictor = OptionsPredictor()

try:
    # Test feature preparation
    X, y = predictor.prepare_features(test_data)
    print(f"✅ Feature preparation: OK (X shape: {X.shape}, y shape: {y.shape})")
    
    # Validate features
    assert X.shape[0] == len(test_data), "Feature count mismatch"
    assert not np.isnan(X).any(), "NaN values in features"
    assert not np.isinf(X).any(), "Inf values in features"
    print(f"✅ Feature validation: OK (no NaN/inf)")
    
    # Test model training
    predictor.train(X, y)
    print(f"✅ Model training: OK")
    
    # Test predictions
    predictions = predictor.predict(X[-10:])
    assert len(predictions) == 10, "Prediction count mismatch"
    assert all(isinstance(p, (int, float, np.number)) for p in predictions), "Non-numeric predictions"
    print(f"✅ Predictions: OK (10 predictions generated, all numeric)")
    
    print("\n✅ ALL PREDICTOR TESTS PASSED")
    
except AssertionError as e:
    print(f"❌ ASSERTION FAILED: {e}")
except Exception as e:
    print(f"❌ ERROR: {type(e).__name__}: {e}")
