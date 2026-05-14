---
name: test-analytics-accuracy
description: "Use when: running comprehensive accuracy tests on analytics modules to validate predictions, Greeks calculations, sentiment scoring, and volume detection against existing datasets."
---

# Test Analytics Accuracy

This skill runs comprehensive debugging and validation workflows for your stock options analytics pipeline.

## Included Tests

### 1. **Predictor Accuracy Test**
Tests the ML model against historical price data:
```bash
# Run: /test_predictor_accuracy.py
# Validates:
# - Model trains without errors
# - Predictions are numeric and within reasonable ranges
# - Feature engineering works correctly
# - Model maintains target accuracy threshold
```

### 2. **Greeks Validation Test**
Verifies Black-Scholes calculations against known benchmarks:
```bash
# Run: /test_greeks_validation.py
# Validates:
# - Delta values (0 to 1 for calls, -1 to 0 for puts)
# - Gamma is always positive
# - Theta decay follows expected patterns
# - Vega and rho scale appropriately
# - Handles edge cases (near expiration, deep ITM/OTM)
```

### 3. **Sentiment Consistency Test**
Checks sentiment scoring consistency and confidence calculation:
```bash
# Run: /test_sentiment_consistency.py
# Validates:
# - Scores range from -1 to +1
# - Confidence is 0-100 percentage
# - Articles with similar tone get similar scores
# - Fallback works when API unavailable
```

### 4. **Volume Detection Test**
Tests anomaly detection with known volume patterns:
```bash
# Run: /test_volume_detection.py
# Validates:
# - Z-scores calculated correctly
# - Anomaly thresholds work as expected
# - Put/Call ratios handle edge cases
# - Volume trends identified accurately
```

## Quick Start

### Run All Tests
```bash
python test_all_analytics.py
```

### Run Specific Module Test
```bash
python test_predictor_accuracy.py
python test_greeks_validation.py
python test_sentiment_consistency.py
python test_volume_detection.py
```

### Debug Failing Test
1. Check test output for specific failure point
2. Review test expectations in `/tests/` directory
3. Compare against recent code changes in relevant module
4. Run focused test: `python -m pytest test_<module> -v`

## Test Data

Sample datasets are located in `/tests/data/`:
- `sample_price_data.csv`: 100 days of OHLCV data
- `known_greeks_benchmarks.json`: Precalculated Greeks for validation
- `sentiment_samples.txt`: Sample news headlines with expected scores
- `volume_patterns.csv`: Historical volume with known anomalies

## Interpreting Results

| Result | Meaning | Action |
|--------|---------|--------|
| ✅ PASS | Function behaves correctly | No action needed |
| ⚠️ WARN | Non-critical deviation | Review logic, may be acceptable |
| ❌ FAIL | Test expectation not met | Review changes, fix implementation |
| 🔴 ERROR | Exception or crash | Check error message, validate inputs |

## Common Issues & Fixes

**Issue**: "Feature 'RSI_14' not found"
- **Fix**: Ensure data preprocessing adds all required technical indicators before passing to predictor

**Issue**: Greeks calculations are NaN
- **Fix**: Verify input parameters: S > 0, K > 0, T > 0, sigma > 0

**Issue**: Volume anomaly always returns False
- **Fix**: Check window size isn't larger than data length; verify threshold_sigma > 0

**Issue**: Sentiment score is always neutral
- **Fix**: Verify NewsAPI key is valid; check internet connection for API calls

## Custom Test Creation

To add tests for your specific use case:

1. Copy test template: `cp /tests/test_template.py /tests/test_custom.py`
2. Define test data and expected outcomes
3. Run: `python /tests/test_custom.py`
4. Integrate into `test_all_analytics.py` for regular validation

## Accuracy Targets

Current expected performance:
- **Predictor**: 100% test accuracy maintained
- **Greeks**: Within 0.1% of benchmark values
- **Sentiment**: Consistent scoring across similar articles
- **Volume**: Detect real anomalies with > 95% precision

Modifications should preserve these targets or document why changes are acceptable.
