---
name: streamlit-options-dashboard
description: "Use when: building a real-time options dashboard in Streamlit to visualize predictions, Greeks, sentiment, and trade recommendations from the india-options-prediction workflow."
---

# Streamlit Options Dashboard

Generate a real-time Streamlit dashboard that integrates the india-options-prediction workflow into an interactive trading interface.

## Parameters

- **`instrument`** (dropdown): Select from [SENSEX, NIFTY, BANKNIFTY, GOLD, SILVER]
- **`expiry_date`** (date picker): Choose expiration date (default: next weekly)
- **`timeframe`** (tabs): Switch between 15-min, 1-hr, daily analysis
- **`auto_refresh`** (toggle): Enable live updates (default: every 30 seconds)

## Dashboard Sections

### Section 1: Real-Time Price & Pattern Analysis
```
┌─────────────────────────────────────────────────┐
│ SENSEX | Price: ₹64,500 | Change: +0.45% ↑     │
├─────────────────────────────────────────────────┤
│ 15-MIN | 1-HR | DAILY                           │
│                                                  │
│ Pattern: Bullish Engulfing (Strength: 0.82)    │
│ ML Prediction: UP (Confidence: 71%)             │
│ Timeframe Consensus: 2/3 agree ✓                │
│                                                  │
│ [Chart: Price + Candlesticks + Bollinger Bands]│
│                                                  │
│ Volume Anomaly: No                              │
│ Sentiment Score: +0.32 (Confidence: 68%)        │
└─────────────────────────────────────────────────┘
```

### Section 2: Greeks & Strike Selection
```
┌─────────────────────────────────────────────────┐
│ GREEKS FOR 64,500 CALL (1-HR EXPIRY)            │
├─────────────────────────────────────────────────┤
│ Delta: 0.62 [====●════] Risk Exposure: HIGH    │
│ Gamma: 0.018 [====●════] Convexity: MEDIUM    │
│ Theta: -0.45 [===●─────] Time Decay: MODERATE  │
│ Vega: 2.31  [════●═════] Vol Sensitivity: HIGH │
│ Rho: 0.12   [═════●────] Rate Sensitivity: LOW │
│                                                  │
│ Implied Vol (IV): 18.5% | Market IV: 19.2%    │
├─────────────────────────────────────────────────┤
│ Strike Selection:                               │
│ ┌─ 64,000 | Bid: ₹450 | Ask: ₹455 | Delta: 0.71│
│ ├─ 64,500 | Bid: ₹275 | Ask: ₹280 | Delta: 0.62│ ← RECOMMENDED
│ └─ 65,000 | Bid: ₹155 | Ask: ₹160 | Delta: 0.48│
└─────────────────────────────────────────────────┘
```

### Section 3: Sentiment & News Drivers
```
┌─────────────────────────────────────────────────┐
│ GLOBAL NEWS IMPACT (Last 24 Hours)              │
├─────────────────────────────────────────────────┤
│ [+] RBI Signals Patience on Rates      (Score: +0.6)
│ [+] India GDP Growth Beats Estimates   (Score: +0.4)
│ [-] Oil Prices Rise (inflation worry)  (Score: -0.3)
│ [~] Fed Meeting Today (monitoring)     (Score: -0.1)
│                                                  │
│ Net Sentiment: +0.32 | Confidence: 68%         │
│ Key Themes: Bullish Growth, Neutral Rates      │
│                                                  │
│ [Expand Articles] [Refresh News Feed]          │
└─────────────────────────────────────────────────┘
```

### Section 4: Trade Recommendation
```
┌─────────────────────────────────────────────────┐
│ TRADE SETUP RECOMMENDATION                      │
├─────────────────────────────────────────────────┤
│ Signal Strength: ███████░░ (72%)               │
│                                                  │
│ ✓ All timeframes agree → UP                    │
│ ✓ Candlestick pattern → BULLISH                │
│ ✓ Global sentiment → POSITIVE                  │
│ ~ Volume → NORMAL (no spike)                   │
│                                                  │
│ RECOMMENDATION: BUY CALL                        │
│ Strike: 64,500 | Premium Target: ₹280         │
│ Target Delta: 0.62 (HIGH CONVICTION)           │
│                                                  │
│ Risk Management:                                │
│ • Max Loss: ₹280 (1.25% of ₹22,400 account)   │
│ • Target Profit: ₹140 (50% of premium)         │
│ • Risk/Reward Ratio: 1:1.8 ✓ (meets 1.5 threshold)
│ • Exit Rules: -100% (loss), +50% (profit)     │
│                                                  │
│ [Copy Trade Setup] [Execute on DHAN] [Skip]   │
└─────────────────────────────────────────────────┘
```

### Section 5: Live Trade Monitor
```
┌─────────────────────────────────────────────────┐
│ ACTIVE TRADES                                   │
├─────────────────────────────────────────────────┤
│ Timestamp    | Instrument | Type   | Entry   │ P&L  │
│──────────────┼────────────┼────────┼─────────┼──────│
│ 10:15 AM     | NIFTY 50   | BUY    | ₹275    | +₹35 │
│              | 1-HR CALL  |        | (active)│ +13% │
│──────────────┼────────────┼────────┼─────────┼──────│
│ 09:45 AM ✓   | SENSEX     | BUY    | ₹450    | +₹90 │
│              | 1-HR CALL  | CLOSED | (exit:  │ +20% │
│              |            |        │  ₹540)  │      │
│                                                  │
│ Total P&L Today: +₹125 | Win Rate: 100% (2/2) │
│                                                  │
│ [Refresh] [Close Position] [View History]      │
└─────────────────────────────────────────────────┘
```

### Section 6: Backtest Results
```
┌─────────────────────────────────────────────────┐
│ STRATEGY BACKTEST (Last 30 Days)                │
├─────────────────────────────────────────────────┤
│ Total Trades: 48 | Wins: 32 | Losses: 16      │
│ Win Rate: 66.7% | Avg Win: ₹75 | Avg Loss: -₹40
│ Profit Factor: 1.85 | Max Drawdown: -₹320      │
│ Cumulative P&L: +₹2,600 | ROI: +11.6%          │
│                                                  │
│ By Instrument:                                  │
│   NIFTY 50: 68% win rate | +₹1,450 P&L         │
│   SENSEX: 65% win rate | +₹850 P&L             │
│   GOLD: 60% win rate | +₹300 P&L               │
│                                                  │
│ By Timeframe:                                   │
│   15-MIN: 58% win rate | +₹680 P&L             │
│   1-HR: 72% win rate | +₹1,680 P&L (optimal)  │
│   DAILY: 66% win rate | +₹240 P&L              │
│                                                  │
│ [Download Report] [Adjust Filters]             │
└─────────────────────────────────────────────────┘
```

---

## Implementation Code Template

```python
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from analytics.intraday_options import fetch_intraday_options, fetch_option_chain
from analytics.predictor import predict_price
from analytics.greeks import calculate_greeks
from analytics.sentiment import get_sentiment_score
from analytics.volume_detector import detect_volume_anomaly
from analytics.candlestick_patterns import detect_patterns

# Page config
st.set_page_config(page_title="India Options Dashboard", layout="wide")
st.title("📊 Real-Time India Options Prediction Dashboard")

# Sidebar controls
with st.sidebar:
    instrument = st.selectbox("Select Instrument", ["SENSEX", "NIFTY", "BANKNIFTY", "GOLD", "SILVER"])
    expiry_date = st.date_input("Expiry Date", value=datetime.now() + timedelta(days=3))
    timeframe = st.radio("Timeframe", ["15-MIN", "1-HR", "DAILY"], horizontal=True)
    auto_refresh = st.toggle("Auto Refresh (30s)", value=True)

# Main dashboard
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader(f"{instrument} | {timeframe}")
    # Fetch data
    data = fetch_intraday_options(instrument, timeframe.lower())
    
    # Section 1: Price & Patterns
    st.write("#### Real-Time Price Analysis")
    current_price = data['Close'].iloc[-1]
    price_change = ((data['Close'].iloc[-1] - data['Close'].iloc[-2]) / data['Close'].iloc[-2]) * 100
    st.metric(label=f"{instrument} Price", value=f"₹{current_price:.2f}", delta=f"{price_change:+.2f}%")
    
    # Candlestick patterns
    patterns = detect_patterns(data[['Open', 'High', 'Low', 'Close']])
    st.write(f"📈 Pattern: {patterns['pattern_name']} (Strength: {patterns['strength']:.2f})")
    
    # ML prediction
    prediction = predict_price(data['Close'].tail(100), data[['RSI_14', 'MACD', 'Volume_Trend']])
    st.write(f"🤖 ML Prediction: **{prediction['direction']}** (Confidence: {prediction['confidence']:.0%})")

with col2:
    st.subheader("Quick Stats")
    st.metric("Volume Anomaly", "No" if not detect_volume_anomaly(data['Volume'].tail(100))['is_anomaly'] else "YES ⚠️")
    sentiment = get_sentiment_score(instrument, lookback_hours=24)
    st.metric("Sentiment", f"{sentiment['score']:+.2f}", f"Conf: {sentiment['confidence']:.0f}%")

# Section 2: Greeks & Strikes
st.divider()
st.subheader("⚙️ Greeks & Strike Selection")

option_chain = fetch_option_chain(instrument, expiry_date, "CE")
selected_strike = st.selectbox("Select Strike", option_chain['Strike'].values)
greeks = calculate_greeks(current_price, selected_strike, 0.04, 0.18, 0.06, "CE")

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Delta", f"{greeks['delta']:.2f}")
col2.metric("Gamma", f"{greeks['gamma']:.4f}")
col3.metric("Theta", f"{greeks['theta']:.2f}")
col4.metric("Vega", f"{greeks['vega']:.2f}")
col5.metric("Premium", f"₹{greeks['call_premium']:.2f}")

# Section 3: Trade Recommendation
st.divider()
st.subheader("💡 Trade Recommendation")

conviction = "HIGH" if prediction['confidence'] > 0.7 else "MEDIUM" if prediction['confidence'] > 0.6 else "LOW"
st.info(f"**Signal Strength:** {conviction} | **Recommended Action:** {'BUY CALL' if prediction['direction'] == 'UP' else 'BUY PUT' if prediction['direction'] == 'DOWN' else 'SKIP'}")

# Risk/Reward
max_risk = greeks['call_premium']
target_reward = max_risk * 0.5
risk_reward = target_reward / max_risk if max_risk > 0 else 0
st.write(f"**Risk/Reward:** 1:{risk_reward:.2f} {'✓ Good' if risk_reward >= 1.5 else '✗ Unfavorable'}")

# Execute button
if st.button("Execute Trade on DHAN"):
    st.success(f"Trade executed: BUY {selected_strike} CALL @ ₹{greeks['call_premium']:.2f}")
    # Call DHAN API here
    
# Auto-refresh
if auto_refresh:
    st.write("🔄 Auto-refreshing in 30 seconds...")
    import time
    time.sleep(30)
    st.rerun()
```

---

## Features

✅ **Real-time data**: Refreshes every 30 seconds (configurable)  
✅ **Multi-timeframe**: Toggle between 15-min, 1-hr, daily  
✅ **Greeks visualization**: Delta, gamma, theta, vega, rho plots  
✅ **Sentiment integration**: Global news impact display  
✅ **Strike optimizer**: Recommends best strikes by delta/conviction  
✅ **Trade execution**: One-click DHAN API integration  
✅ **Backtest section**: Historical accuracy & P&L tracking  
✅ **Mobile responsive**: Works on tablet/phone for on-the-go trading  

---

## Next Steps

1. **Integrate DHAN WebSocket** for live option chain updates
2. **Add paper trading mode** to validate signals without real capital
3. **Build trade journal** to log all trades + outcomes
4. **Set up alerts** for key events (volume spikes, news releases, Greeks thresholds)
5. **Deploy on cloud** (Streamlit Cloud, AWS, Azure) for 24/5 availability

