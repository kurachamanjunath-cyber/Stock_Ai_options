---
description: "Use when: building or modifying options prediction code in analytics/ directory. Enforces options-specific data validation, Greeks constraints, premium accuracy, and compliance with India market standards."
applyTo: "analytics/**"
---

# India Options Prediction Code Standards

## Options Premium Validation

All modules returning option premiums must enforce:
```python
# Call premium constraint
assert call_premium >= intrinsic_value_call, "Call premium below intrinsic value"
assert call_premium < spot_price * 0.1, "Call premium exceeds 10% of spot"

# Put premium constraint  
assert put_premium >= intrinsic_value_put, "Put premium below intrinsic value"
assert put_premium < strike_price * 0.1, "Put premium exceeds 10% of strike"

# Bid-ask spread (realistic for India options)
assert bid_price > 0 and ask_price > bid_price, "Invalid bid-ask spread"
assert (ask_price - bid_price) / mid_price < 0.05, "Spread > 5% suggests stale data"
```

## Greeks Calculation Requirements

### Black-Scholes Constraints
- **Time to expiry (T)**: Must be > 0; validate against market expiry dates
  - 15-min options: T ∈ (0, 0.01] days
  - 1-hr options: T ∈ (0, 0.04] days  
  - Daily options: T ∈ (0, 1] days
- **Spot price (S)**: Must be > 0; validate against real-time market data
- **Strike price (K)**: Must be > 0; must exist in option chain
- **Volatility (σ)**: Must be in [0.05, 1.0] (5%-100% IV range for India derivatives)
- **Risk-free rate (r)**: Must be in [0.02, 0.10] (2%-10% typical RBI rates)

### Greeks Output Validation
```python
# Delta: directional exposure (probability of ITM)
assert 0 <= delta_call <= 1, "Call delta out of range [0, 1]"
assert -1 <= delta_put <= 0, "Put delta out of range [-1, 0]"

# Gamma: delta's rate of change (always positive)
assert gamma > 0, "Gamma must be positive (convexity)"
assert gamma < delta_call / (spot * 0.01), "Gamma unreasonably high"

# Theta: daily time decay (negative for buyer, positive for seller)
assert theta < 0 for buyer_position, "Theta should be negative for buyers"
assert abs(theta) < premium / 10, "Daily theta loss > 10% of premium"

# Vega: sensitivity to IV (positive for long options)
assert vega > 0, "Vega must be positive"
assert vega < spot_price * 0.01, "Vega unreasonably high"

# Rho: sensitivity to interest rates
assert abs(rho) < spot_price * 0.001, "Rho unreasonably high"
```

## Sentiment Score Validation

Sentiment module outputs must meet:
- **Score range**: Strictly [-1, +1]; -1 = bearish, 0 = neutral, +1 = bullish
- **Confidence**: [0, 100] percentage; minimum 50% for trade signals
- **Article count**: At least 2 articles required for confidence > 50%
- **Recency**: Articles ≤ 24 hours old for daily options, ≤ 4 hours for intraday

```python
assert -1 <= sentiment_score <= 1, "Sentiment score out of [-1, 1]"
assert 0 <= confidence <= 100, "Confidence out of [0, 100]"
assert len(articles) >= 2 if confidence > 50 else True, "Insufficient articles"
assert all(article['timestamp'] > now - timedelta(hours=lookback_hours) for article in articles)
```

## Volume Anomaly Detection Rules

Z-score based anomaly detection must validate:
- **Window size**: ≥ 20 periods (captures 3-4 weeks of data)
- **Z-score threshold**: [1.0, 3.0] range (1.0 = 68% of samples, 3.0 = 99.7%)
- **Anomaly ratio**: Valid when volume > 1.3x historical average
- **Zero-volume handling**: Cannot divide by zero; return error dict instead

```python
def detect_volume_anomaly(volume_data, threshold=2.0, window=20):
    assert len(volume_data) >= window, "Insufficient data for window"
    assert threshold > 0 and threshold <= 3.0, "Invalid Z-score threshold"
    
    if avg_volume == 0:
        return {"error": "Zero volume history; cannot detect anomaly"}
    
    z_score = (current_volume - mean) / std_dev
    is_anomaly = z_score > threshold
    return {
        "is_anomaly": is_anomaly,
        "ratio": current_volume / avg_volume,
        "z_score": z_score,
        "confidence": min(95 if is_anomaly else 60)
    }
```

## Predictor Model Validation

Machine learning predictions must:
- **Input check**: No NaN/Inf values in price history or features
- **Feature check**: Verify all required features exist (RSI_14, MACD, Volume_Trend, etc.)
- **Output format**: Return {"direction": "UP"|"DOWN"|"NEUTRAL", "confidence": float}
- **Confidence range**: [0, 1] where 0.5+ indicates tradeable signal
- **Prediction horizon**: State time horizon (15-min, 1-hr, daily) explicitly

```python
def predict_price(price_history, features, target="directional"):
    # Validate inputs
    assert len(price_history) >= 100, "Insufficient training data"
    assert not price_history.isna().any(), "NaN values in price history"
    assert all(feat in features.columns for feat in REQUIRED_FEATURES), "Missing features"
    
    prediction = model.predict(features.tail(1))
    confidence = model.predict_proba(features.tail(1)).max()
    
    assert 0 <= confidence <= 1, "Confidence out of [0, 1]"
    assert prediction in ["UP", "DOWN", "NEUTRAL"], "Invalid prediction"
    
    return {
        "direction": prediction,
        "confidence": confidence,
        "target": "directional",
        "horizon": "1-hr"  # Explicit time horizon
    }
```

## Intraday Options Data Fetching

Real-time options chain data must validate:
- **Strikes**: Cover ±5% around current spot price (at least 5 OTM calls, 5 OTM puts)
- **Bid-ask**: Bid < Ask for all strikes (reject stale quotes)
- **Open Interest**: Non-negative; flag low-OI strikes (< 100 contracts) as illiquid
- **IV Surface**: Monotonic increase away from ATM (normal skew); alert if inverted
- **Data freshness**: Timestamp within last 5 minutes for real-time trading

```python
def fetch_option_chain(instrument, expiry_date, option_type):
    # Fetch and validate
    chain = api.get_option_chain(instrument, expiry_date)
    
    # Strike coverage check
    spot = chain['spot_price'].iloc[0]
    otm_calls = chain[chain['Strike'] > spot]
    assert len(otm_calls) >= 5, "Insufficient OTM calls for trading"
    
    # Bid-ask validity
    assert all(chain['Bid'] < chain['Ask']), "Invalid bid-ask spreads detected"
    
    # Liquidity check
    illiquid_strikes = chain[chain['OpenInterest'] < 100]
    if len(illiquid_strikes) > 0:
        print(f"Warning: {len(illiquid_strikes)} illiquid strikes (OI < 100)")
    
    # Data freshness
    assert (datetime.now() - chain['Timestamp']).total_seconds() < 300, "Data > 5 min old"
    
    return chain
```

## Performance Benchmarks

All modules must meet:
- **Predictor**: Train/predict cycle completes in < 5 seconds
- **Greeks**: Single strike calculation < 10ms
- **Sentiment**: API call with retry/timeout in < 5 seconds
- **Volume**: Anomaly detection on 1000+ data points in < 100ms
- **Intraday Options**: Fetch + parse option chain in < 2 seconds

## Error Handling & Fallbacks

**Never fail silently:**
```python
# BAD: Raises exception and breaks workflow
premium = calculate_call_premium(...)  # Might crash

# GOOD: Return error dict with fallback
try:
    premium = calculate_call_premium(...)
except Exception as e:
    return {
        "error": f"Greeks calculation failed: {str(e)}",
        "fallback_premium": last_known_premium,
        "timestamp": datetime.now()
    }
```

**Fallback strategy:**
- Greeks fail → Use bid price as fallback premium
- Sentiment API timeout → Fallback to neutral (score = 0, confidence = 0)
- Volume data insufficient → Skip anomaly detection; assume normal volume
- Prediction model error → Return NEUTRAL direction (confidence = 0)

## Testing Checklist

Before committing changes to any analytics module:
- [ ] All assertions pass with sample India options data
- [ ] Greeks match benchmark values (testable against known premiums)
- [ ] Edge cases handled: Near-expiry, deep ITM/OTM, zero volume, API timeouts
- [ ] Data freshness validated for 15-min, 1-hr, and daily expirations
- [ ] Error messages are informative and suggest fixes
- [ ] Performance benchmarks met (see Performance Benchmarks section)

