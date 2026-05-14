---
description: "Use when: modifying code in analytics/ directory. Ensures data validation, accuracy testing, and module integration standards."
applyTo: "analytics/**"
---

# Analytics Module Guidelines

## Data Validation Standards
All analytics modules must validate inputs and handle edge cases:

### Predictor Module
- **Input validation**: Check for NaN/inf values, non-positive targets
- **Feature validation**: Verify all required features (RSI_14, MACD, Volume_Trend, etc.) exist
- **Output validation**: Predictions must be numeric and reasonable for price ranges
- **Test data**: Always test with historical price data (e.g., last 100 days)

### Greeks Module
- **Input constraints**: S > 0, K > 0, T > 0, 0 < sigma < 1, 0 < r < 0.5
- **Edge cases**: Handle T ≤ 0, sigma = 0, prices = 0 gracefully
- **Output format**: All Greeks must return as dict with numeric values or error key
- **Validation**: Call premium must be ≥ intrinsic value

### Sentiment Module
- **API handling**: Gracefully handle missing/failed NewsAPI calls
- **Score range**: All sentiment scores must be -1 to +1
- **Confidence**: Must be 0-100 percentage; high when articles agree
- **Articles**: Return at least headline, sentiment, source, timestamp

### Volume Detector Module
- **Window size**: Must be ≤ len(volume_data); validate window parameter
- **Z-score validation**: Anomaly threshold must be > 0
- **Ratio calculation**: Handle div-by-zero when avg_volume = 0
- **Put/Call ratio**: Must handle zero volumes without crashing

## Testing Requirements
Before committing changes:

```python
# Test with sample data
import pandas as pd
data = pd.DataFrame({
    'Close': [100, 101, 102, 103, 104],
    'Volume': [1000000, 1100000, 900000, 1200000, 800000]
})
# Run your function and verify no errors
```

## Module Integration Rules
- **Imports**: Use relative imports within analytics package (`from . import greeks`)
- **Dependencies**: All packages must be in requirements.txt
- **Return types**: Always return dicts with explicit keys (no tuples or arbitrary objects)
- **Docstrings**: Include Args, Returns, Raises sections with type hints

## Performance Considerations
- Predictor: Train/predict cycle should complete in < 5 seconds
- Greeks: Single calculation < 10ms
- Sentiment: API call with timeout = 5 seconds
- Volume: Analysis of 1000+ data points in < 100ms

## Error Handling
- Never raise exceptions silently; return error dicts with "error" key
- Log to console with clear messages for debugging
- Always provide fallback values when APIs/data fail
- Include original data diagnostics in error responses
