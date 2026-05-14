# India Options Analytics Code Validation Report
**Generated:** May 13, 2026  
**Validated Against:** [india-options.instructions.md](india-options.instructions.md)

---

## 📊 Summary

| Module | Status | Issues | Priority |
|--------|--------|--------|----------|
| `predictor.py` | ⚠️ NEEDS UPDATES | Missing confidence validation, no horizon specification | HIGH |
| `greeks.py` | ✅ COMPLIANT | Excellent error handling & range validation | — |
| `sentiment.py` | ⚠️ PARTIAL | Missing recency check, low confidence default | MEDIUM |
| `volume_detector.py` | ✅ COMPLIANT | Proper z-score validation, handles zero volumes | — |
| `intraday_options.py` | ⚠️ PARTIAL | Strike liquidity checks missing | MEDIUM |
| `candlestick_patterns.py` | ❓ PENDING | Not fully reviewed yet | — |
| `dhan_integration.py` | ❓ PENDING | Not fully reviewed yet | — |

---

## ✅ **COMPLIANT: `greeks.py`**

### Strengths
✓ **Input validation**: Checks S>0, K>0, T>0, σ>0  
✓ **Error handling**: Returns error dict instead of raising exceptions  
✓ **Greeks ranges**: Delta [0,1] for calls handled correctly  
✓ **Edge case handling**: T≤0, σ≤0 caught explicitly  
✓ **Return format**: Consistent dict with all Greeks keys  

### Code Quality
```python
if T <= 0 or sigma <= 0 or K <= 0 or S <= 0:
    return {"error": "Invalid input parameters"}  # ✓ Proper fallback
```

---

## ⚠️ **NEEDS UPDATES: `predictor.py`**

### Issues Found

**Issue #1: Missing Confidence Validation**  
Current output format doesn't match instructions:
```python
# Current: No confidence range check
# Required: confidence ∈ [0, 1] with explicit validation
```

**Fix Required:**
```python
def predict_price(self, price_history, features, target="directional"):
    # ... existing code ...
    
    # ADD THIS:
    prediction = model.predict(features.tail(1))[0]
    confidence = model.predict_proba(features.tail(1)).max()
    
    # VALIDATE
    assert 0 <= confidence <= 1, f"Confidence {confidence} out of [0, 1]"
    assert prediction in ["UP", "DOWN", "NEUTRAL"], f"Invalid prediction: {prediction}"
    
    return {
        "direction": prediction,
        "confidence": confidence,
        "horizon": "1-hr",  # ← ADD THIS (currently missing)
        "target": target
    }
```

**Issue #2: No Time Horizon Specification**  
Instructions require explicit horizon (15-min, 1-hr, daily).  
Currently returns only direction + score, missing horizon context.

**Issue #3: Insufficient Data Check**  
```python
# Currently: len(data) < 50 check exists ✓
# But: Should also validate NaN/Inf values
```

### Recommended Changes
1. Add `time_horizon` parameter to `predict()` method
2. Validate confidence [0, 1] range before returning
3. Add data quality checks: `assert not np.isnan(X).any()`
4. Return explicit horizon in response dict

---

## ⚠️ **PARTIAL: `sentiment.py`**

### Issues Found

**Issue #1: Missing Article Recency Check**  
Instructions require: Articles ≤ 24 hours old  
Current code: No timestamp validation

```python
# ADD THIS VALIDATION:
def analyze_news_sentiment(self, asset_name, lookback_hours=24, api_key=None):
    # ... existing code ...
    
    for article in articles:
        pub_time = datetime.fromisoformat(article['publishedAt'].replace('Z', '+00:00'))
        age_hours = (datetime.now(timezone.utc) - pub_time).total_seconds() / 3600
        
        assert age_hours <= lookback_hours, f"Article too old: {age_hours}h > {lookback_hours}h"
```

**Issue #2: Low Confidence Default**  
```python
# Current fallback when API fails:
if not sentiment_scores:
    sentiment_scores = [0.1]  # Uses neutral ✓ but confidence will be high (false positive)

# Issue: Confidence is always calculated as high even when API failed
confidence = min(100, (1 - (sentiment_std / 2)) * 100)
# → When only 1 score: sentiment_std=0, confidence=100% (misleading!)

# FIX: Track API failure status
if api_failed:
    confidence = 0  # Low confidence for fallback
```

**Issue #3: Missing Keyword Filtering**  
Instructions require keyword filtering for market drivers.  
Current code: Searches only by asset name.

```python
# ADD: Keyword filtering for India market drivers
keywords = {
    "SENSEX": ["RBI", "rupee", "inflation", "equity"],
    "NIFTY": ["RBI", "India GDP", "emerging markets"],
    "GOLD": ["Fed", "inflation", "geopolitics", "safe-haven"],
    "SILVER": ["industrial demand", "Fed", "inflation"]
}
```

### Recommended Changes
1. Add timestamp validation for articles (≤ lookback_hours)
2. Lower confidence when API fails or insufficient articles
3. Add keyword filtering per instrument
4. Return key_themes array in response

---

## ✅ **COMPLIANT: `volume_detector.py`**

### Strengths
✓ **Proper z-score calculation**: Valid formula & scaling  
✓ **Zero-volume handling**: Checks `if volume_std > 0`  
✓ **Threshold validation**: [1.0, 3.0] range checks possible  
✓ **Anomaly scoring**: 0-100 range properly scaled  
✓ **Error handling**: Returns error dict, doesn't crash  
✓ **Recent trend tracking**: Volume trend detection included  

### Code Quality
```python
if volume_std > 0:
    z_score = (current_volume - avg_volume) / volume_std  # ✓ Safe division
else:
    z_score = 0.0  # ✓ Handles zero case
```

---

## ⚠️ **PARTIAL: `intraday_options.py`**

### Issues Found

**Issue #1: Missing Liquidity Validation**  
Instructions require: Check Open Interest < 100 → flag as illiquid  
Current code: No liquidity checks on strikes

```python
# ADD THIS TO fetch_option_chain:
def fetch_option_chain(self, instrument, expiry_date):
    chain = api.get_option_chain(instrument, expiry_date)
    
    # MISSING: Liquidity validation
    illiquid_strikes = chain[chain['OpenInterest'] < 100]
    if len(illiquid_strikes) > 0:
        logger.warning(f"Illiquid strikes detected: {len(illiquid_strikes)}")
    
    return chain
```

**Issue #2: Bid-Ask Spread Not Validated**  
Instructions require: `(ask_price - bid_price) / mid_price < 5%`  
Current code: No spread validation

```python
# ADD THIS:
assert all(chain['Bid'] < chain['Ask']), "Invalid bid-ask spreads"
spread_pct = (chain['Ask'] - chain['Bid']) / ((chain['Ask'] + chain['Bid']) / 2)
assert all(spread_pct < 0.05), "Spread > 5% suggests stale data"
```

**Issue #3: No Data Freshness Check**  
Instructions require: Timestamp within last 5 minutes  
Current code: No timestamp validation

```python
# ADD THIS:
import time
current_timestamp = chain['Timestamp'].iloc[-1]
time_diff = (datetime.now() - current_timestamp).total_seconds()
assert time_diff < 300, f"Data > 5 min old ({time_diff}s)"
```

### Recommended Changes
1. Add liquidity check (OI < 100 flag as illiquid)
2. Validate bid-ask spread < 5% of mid-price
3. Add data freshness validation (< 5 min old)
4. Log warnings for stale/illiquid strikes

---

## ❓ **NOT YET REVIEWED**

- `candlestick_patterns.py` — Pattern strength validation, edge cases
- `dhan_integration.py` — API response validation, error handling
- `dhan_websocket.py` — Real-time data validation, reconnection logic

---

## 🎯 Action Items (Prioritized)

### 🔴 **HIGH PRIORITY** (Blocks trading)
1. **Update `predictor.py`**: Add horizon specification + confidence validation
2. **Update `intraday_options.py`**: Add bid-ask & liquidity validation

### 🟡 **MEDIUM PRIORITY** (Improves accuracy)
3. **Update `sentiment.py`**: Add recency checks + keyword filtering
4. Update error handling across all modules to match standards

### 🟢 **LOW PRIORITY** (Nice-to-have)
5. Review `candlestick_patterns.py` for edge cases
6. Add comprehensive logging to all modules

---

## ✨ Code Examples for Fixes

Ready to apply these updates to each file? Recommend order:
1. `predictor.py` (high impact)
2. `intraday_options.py` (high impact)
3. `sentiment.py` (medium impact)

Would you like me to generate the complete updated versions of these files?
