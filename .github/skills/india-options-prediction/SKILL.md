---
name: india-options-prediction
description: "Use when: building or validating predictions for India stock indices (Sensex, Nifty, BankNifty) and commodities (Gold, Silver) options—ensuring accurate call/put pricing with directional forecasts and price range estimates."
---

# India Options Prediction Workflow

This skill provides a structured 10-step checklist for predicting accurate call and put option prices for India's major stock indices and commodities. It integrates multi-timeframe analysis, candlestick patterns, global news sentiment, Greeks-based strike selection, volume detection, and risk validation.


## Prerequisites

Ensure these modules are ready before starting:
- **Predictor** (`analytics/predictor.py`): ML model trained on historical price data
- **Greeks** (`analytics/greeks.py`): Black-Scholes calculations for option premiums
- **Sentiment** (`analytics/sentiment.py`): Market sentiment from news sources
- **Volume Detector** (`analytics/volume_detector.py`): Anomaly detection for trading volume
- **Intraday Options** (`analytics/intraday_options.py`): Real-time options data fetching

## Step-by-Step Prediction Checklist

### Step 1: Fetch Current Market Data for Multiple Timeframes
Retrieve real-time price and volume data across your trading horizons:
```python
from analytics.intraday_options import fetch_intraday_options
timeframes = ["15min", "1h", "daily"]  # Your key trading horizons
market_data = {}

for tf in timeframes:
    market_data[tf] = fetch_intraday_options(
        instrument="SENSEX",  # or NIFTY, BANKNIFTY, GOLD, SILVER
        interval=tf
    )
```
**Validation**: Confirm each timeframe has Close, Volume, and timestamp fields; no NaN values in price; data is synced across all timeframes (same spot price).

---

### Step 2: Analyze Candlestick Patterns & Generate Price Predictions
Detect bullish/bearish patterns and combine with ML directional forecasts across timeframes:
```python
from analytics.candlestick_patterns import detect_patterns
from analytics.predictor import predict_price

predictions = {}
for tf in timeframes:
    data = market_data[tf]
    
    # Detect candlestick patterns
    patterns = detect_patterns(data[['Open', 'High', 'Low', 'Close']])
    # Returns: {pattern_name, strength (0-1), direction (UP/DOWN/NEUTRAL)}
    
    # ML prediction
    ml_pred = predict_price(
        price_history=data['Close'].tail(100),
        features=data[['RSI_14', 'MACD', 'Volume_Trend']],
        target="directional"
    )
    
    predictions[tf] = {
        "ml_prediction": ml_pred,  # confidence > 60%
        "pattern": patterns,  # pattern name + strength
        "consensus": "UP" if (ml_pred == "UP" and patterns['direction'] == "UP") else "DOWN" if (ml_pred == "DOWN" and patterns['direction'] == "DOWN") else "NEUTRAL"
    }
```
**Validation**: Consensus across timeframes should align (15-min, 1-hr, daily all signal same direction for high conviction); pattern strength > 0.6 adds confidence.

---

### Step 3: Fetch Global News & Calculate Sentiment Score
Integrate live global news that impacts your instruments to bias directional conviction:
```python
from analytics.sentiment import get_sentiment_score

sentiment = get_sentiment_score(
    instrument="SENSEX",
    lookback_hours=24,  # Last 24 hours of global news
    keywords=["India", "RBI", "global markets", "commodities", "gold", "Fed", "geopolitics"]
)
# Returns: score (-1 to +1), confidence (0-100), articles count, key_themes[]

# Global factors that impact India markets:
# - US inflation/Fed decisions → affects rupee, gold, rates
# - Global equity selloff → risk-off affects Sensex/Nifty
# - Oil/commodity price moves → affects inflation expectations
# - Geopolitical events → flight-to-safety trades in gold/silver
```
**Validation**: Ensure confidence > 50%; track key themes to understand causal drivers; fallback to 0 (neutral) if API fails.

---

### Step 4: Detect Volume Anomalies
Identify if current volume signals unusual activity:
```python
from analytics.volume_detector import detect_volume_anomaly
volume_alert = detect_volume_anomaly(
    volume_data=data['Volume'].tail(100),
    threshold=2.0,  # Z-score threshold
    window=20
)
# Returns: is_anomaly (bool), ratio, confidence
```
**Validation**: High volume anomalies often precede price moves; confirm ratio > 1.5x average.

---

### Step 5: Gather Option Chain Data
Fetch current option strikes and their bid-ask prices:
```python
from analytics.intraday_options import fetch_option_chain
option_chain = fetch_option_chain(
    instrument="SENSEX",
    expiry_date="2026-05-20",  # Next weekly/monthly
    option_type="CE"  # or "PE"
)
# Returns: DataFrame with Strike, Bid, Ask, OpenInterest, IV
```
**Validation**: Ensure bid < ask; strike range covers ±5% of current price.

---

### Step 6: Calculate Greeks & Select Delta Preference by Market Regime
Compute option Greeks flexibly based on market conditions and your risk tolerance:
```python
from analytics.greeks import calculate_greeks

greeks_data = {}
for strike in option_chain['Strike'].unique():
    greeks = calculate_greeks(
        spot_price=data['Close'].iloc[-1],
        strike_price=strike,
        time_to_expiry=0.015,  # 15-min expiry: ~0.01 days; 1-hr: ~0.04 days; daily: ~1 day
        volatility=iv_from_chain,
        risk_free_rate=0.06,
        option_type="CE"
    )
    greeks_data[strike] = greeks

# Flexible delta selection based on market conditions:
if sentiment['confidence'] > 80 and patterns['strength'] > 0.7:
    # HIGH CONVICTION: Use higher delta (0.6-0.8)
    target_delta = 0.7  # More directional exposure
elif volume_alert['is_anomaly'] and ml_pred == "UP":
    # VOLUME SPIKE + DIRECTION: Medium delta (0.4-0.6)
    target_delta = 0.5
else:
    # LOW CONVICTION or NEUTRAL: Safer lower delta (0.2-0.4)
    target_delta = 0.3

# Find strike closest to target delta
best_delta_strike = min(greeks_data.items(), 
    key=lambda x: abs(x[1]['delta'] - target_delta))[0]
```
**Validation**: Delta ∈ [0,1] for calls, [-1,0] for puts; selected delta matches market conviction level.

---

### Step 7: Combine Signals into Price Target
Weight prediction, sentiment, and Greeks to forecast option premium:
```python
# Pseudo-logic:
directional_bias = {
    "UP": +0.5,
    "DOWN": -0.5,
    "NEUTRAL": 0.0
}[prediction]

sentiment_weight = (sentiment['score'] + 1) / 2  # Normalize to [0,1]
volume_boost = 1.2 if volume_alert['is_anomaly'] else 1.0

# Adjust Greeks-based premium based on sentiment & direction
adjusted_premium = greeks['call_premium'] * (1 + 0.1 * directional_bias) * volume_boost
```
**Validation**: Compare adjusted premium to market bid-ask spread; should fall within range for profitable entry.

---

### Step 8: Identify Best Strikes
Select call and put strikes with optimal risk/reward profiles:
```python
# For Directional Trade (prediction-driven):
if prediction == "UP":
    best_call = option_chain.loc[
        (option_chain['Strike'] < spot + 2*ATM_width) & 
        (option_chain['Strike'] > spot - ATM_width)
    ].nsmallest(1, 'Ask')  # Closest OTM call with low premium
    
    recommended_strike_call = best_call['Strike'].iloc[0]
    premium_call = best_call['Ask'].iloc[0]

# For Hedge Trade (pair call + put):
atm_strike = option_chain.loc[option_chain['Strike'].sub(spot).abs().idxmin()]['Strike']
recommended_strike_put = atm_strike
```
**Validation**: Ensure max loss (premium paid) < 5% of account; delta ratio aligns with conviction.

---

### Step 9: Validate Against Risk Criteria
Confirm trade setup meets risk management standards:
```python
call_premium = recommended_premium_call
put_premium = recommended_premium_put
spot_price = data['Close'].iloc[-1]

max_risk = min(call_premium, put_premium)
max_reward = abs(strike_call - strike_put) - max_risk
risk_reward_ratio = max_reward / max_risk

# Checks:
assert risk_reward_ratio >= 1.5, "Unfavorable risk/reward"
assert call_premium < 0.02 * spot_price, "Premium too high"
assert greeks['delta'] > 0.3, "Insufficient directional exposure"
```
**Validation**: All assertions pass; skip trade if any fails.

---

### Step 10: Log Prediction & Monitor
Record the prediction setup and monitor real-time outcome:
```python
trade_log = {
    "timestamp": datetime.now(),
    "instrument": "SENSEX",
    "expiry": "2026-05-20",
    "direction": prediction,
    "sentiment_score": sentiment['score'],
    "volume_anomaly": volume_alert['is_anomaly'],
    "recommended_call_strike": strike_call,
    "recommended_call_premium": premium_call,
    "recommended_put_strike": strike_put,
    "recommended_put_premium": premium_put,
    "greeks": greeks,
    "risk_reward_ratio": risk_reward_ratio
}
# Save to CSV or database for backtesting
```
**Validation**: Log is complete and timestamped; no missing fields.

---

## Quick Decision Tree (Multi-Timeframe & Global News)

```
CONVICTION FILTER:
├─ All timeframes (15-min, 1-hr, daily) consensus UP + Global sentiment positive?
│  └─ HIGH CONVICTION
│     ├─ Volume spike detected? → BUY CALL (delta 0.6-0.8, high gamma for profits)
│     └─ Normal volume → BUY CALL (delta 0.4-0.6) or CALL SPREAD for less capital
│
├─ 2/3 timeframes agree + mixed global news?
│  └─ MEDIUM CONVICTION
│     ├─ Candlestick pattern strong (>0.7)? → BUY CALL (delta 0.3-0.5, safer)
│     └─ Weak pattern (<0.5)? → SKIP or SMALL POSITION
│
└─ Timeframes disagreed or global news negative?
   └─ LOW CONVICTION / AVOID DIRECTIONAL TRADE
      ├─ High volume anomaly only? → Consider STRADDLE (buy ATM call + put)
      └─ Normal environment → SKIP or wait for next signal

TRADE STRUCTURE BY TIMEFRAME:
├─ 15-min expiry: Smallest premiums, use if pattern strength > 0.8
├─ 1-hr expiry: Optimal balance of theta decay + pattern stability
└─ Daily expiry: Use for longer-term conviction trades, less affected by noise

EXIT RULES:
├─ Profit target: 30-50% of max premium paid
├─ Stop loss: -100% (total loss) on directional bet
├─ Time decay: Close 5 min before expiry if still holding
└─ Sentiment reversal: Exit immediately if global news turns negative
```

---

## Common Pitfalls & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| Timeframe disagreement (15-min UP, daily DOWN) | Noise in lower timeframes vs trend in higher | Rely on 1-hr + daily consensus; skip if <2/3 agree |
| Global news impact missed | News released between 15-min candles | Check news timestamps; re-fetch sentiment every 30-min |
| Premiums mismatch to Greeks | Stale IV or outdated Greeks | Recalculate Greeks with latest IV from option chain every 5 min |
| Wrong strike selected | Over-aggressive directional assumption | Use dynamic delta targeting; select ATM ± 1-2 strikes only |
| Model fails on weekends | Market closed; data stale | Skip predictions when market is closed; check trading hours |
| Sentiment API timeout | NewsAPI rate limit or no articles | Fallback sentiment to 0 (neutral); don't block trade |
| Volume not detected | Window size too small or threshold too high | Use 20+ day window; adjust Z-score threshold to 1.5 |
| Gold/Silver trade fails | Fed decision released; volatility spike | Monitor Fed calendar; reduce position size on news days |
| Trade at exact expiry | Theta decay accelerates in final minutes | Close 5 minutes before expiry; don't hold through close |
| Commodity basis ignored | Gold in INR vs USD; conversion risk | Track INR/USD rate; adjust premiums for FX exposure |

---

## Testing Your Predictions

Run this after completing all 10 steps:
```bash
python /test_predictor_accuracy.py
python /test_greeks_validation.py
python /test_sentiment_consistency.py
python /test_volume_detection.py
```

Then backtest against historical options prices to validate the workflow's edge cases and profitability.

---

## Supported Instruments & Trading Horizons

**Stock Indices** (typically higher volume & tighter spreads):
- **Sensex** (BSE 30): 15-min, 1-hr, daily options available
- **Nifty 50**: 15-min, 1-hr, daily options; most liquid
- **Bank Nifty**: 15-min, 1-hr, daily options; high volatility

**Commodities** (metals tied to global news & geopolitical events):
- **Gold** (MCX / NCDEX): Highly sensitive to Fed policy, USD movement, geopolitics
- **Silver** (MCX / NCDEX): More volatile than gold, driven by industrial demand + safe-haven flows

**Global News Drivers:**
- RBI Policy decisions → affects rupee, equity indices
- Fed/ECB meetings → affects interest rates, gold demand
- Oil prices → affects inflation expectations, Sensex
- Geopolitical events → flight-to-safety in gold/silver
- Global PMI data → affects emerging market inflows

---

## Try These Prompts

1. **"Use india-options-prediction to predict Nifty 50 call prices for 1-hr expiry"** — Full workflow walkthrough
2. **"Which candlestick patterns should I prioritize in step 2?"** — Pattern-specific guidance
3. **"How do I integrate global news into the sentiment score (step 3)?"** — News customization
4. **"What Greeks make sense for a 15-min scalp vs. a daily swing trade?"** — Strategy-specific Greeks
5. **"Run india-options-prediction on Gold with today's geopolitical news"** — Real-world scenario

---

## Related Customizations to Build Next

1. **File Instruction** (`india-options.instructions.md`)  
   Apply to all analytics modules to enforce options-specific data validation (premiums ≥ intrinsic value, IV ranges, etc.)

2. **Custom Agent** (`india-options-specialist.agent.md`)  
   Specializes in debugging failed predictions, with restricted tool access for live trading safeguards

3. **Streamlit Integration Prompt** (`.github/prompts/streamlit-options-dashboard.prompt.md`)  
   Parameterized prompt for building a real-time options dashboard with this skill's workflow

4. **Backtesting Hook** (`options-backtest.json`)  
   Auto-runs accuracy tests on historical data before you trade live
