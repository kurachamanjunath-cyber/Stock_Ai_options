# India Options Dashboard - Setup & Usage Guide

## 📊 Overview

The **India Options Dashboard** is a real-time Streamlit web application that integrates:
- Machine Learning price predictions
- Black-Scholes Greeks calculations
- Market sentiment analysis
- Volume anomaly detection
- Candlestick pattern recognition
- Trade recommendation engine

**File**: [`dashboard.py`](dashboard.py)  
**Framework**: Streamlit  
**Analytics**: Python (scikit-learn, NumPy, Pandas, SciPy)

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Install required packages
pip install streamlit pandas numpy plotly scikit-learn scipy textblob requests

# Or use requirements.txt
pip install -r requirements.txt
```

### 2. Run the Dashboard

```bash
streamlit run dashboard.py
```

The dashboard will open in your browser at: **`http://localhost:8501`**

---

## 📋 Dashboard Features

### Section 1: Real-Time Price & Patterns 📈
- **Live price display** with 24-hour high/low
- **Candlestick chart** with Bollinger Bands
- **Volume analysis** with SMA overlay
- **Pattern detection**: Bullish/Bearish patterns with strength score

### Section 2: ML Predictions 🤖
- **Model training status**: RF model accuracy (R² score)
- **Training metrics**: Sample counts, convergence status
- **Directional forecasts**: UP / DOWN / NEUTRAL signals
- **Confidence scoring**: [0, 1] range with validation

### Section 3: Sentiment & News 📰
- **Sentiment gauge**: -1 (bearish) to +1 (bullish)
- **Confidence levels**: Article count + timestamp recency
- **Market drivers**: RBI, Fed, geopolitics, USD/INR
- **Key themes**: Extracted from news articles

### Section 4: Greeks & Strikes ⚙️
- **Greeks visualization**: Delta, Gamma, Theta, Vega, Rho
- **Call/Put premiums**: Calculated via Black-Scholes
- **Strike selector**: Adjust strike with slider
- **Time decay tracking**: Days to expiry

### Section 5: Volume Analysis 📊
- **Anomaly detection**: Z-score based with threshold
- **Volume ratio**: Current vs. 20-day average
- **Trend identification**: INCREASING / DECREASING
- **Anomaly score**: 0-100% confidence

### Section 6: Trade Recommendations 💡
- **Conviction levels**: HIGH / MEDIUM / LOW
- **Trade signals**: BUY CALL / BUY PUT / SKIP
- **Risk/Reward ratios**: Min 1.5:1 for trades
- **One-click execution**: Ready for DHAN API integration

### Section 7: Backtest Results 📈
- **30-day performance**: Win rate, profit factor, ROI
- **By instrument**: Nifty, Sensex, Gold, Silver
- **By timeframe**: 15-min, 1-hr, daily comparison
- **Drawdown analysis**: Max loss tracking

---

## ⚙️ Configuration

### Sidebar Controls

| Control | Options | Purpose |
|---------|---------|---------|
| **Instrument** | NIFTY, SENSEX, BANKNIFTY, GOLD, SILVER | Select index/commodity |
| **Timeframe** | 15-MIN, 1-HR, DAILY | Analysis horizon |
| **Expiry Date** | Date picker | Options expiry selection |
| **Auto Refresh** | Toggle | Enable 30-second updates |
| **Strike Interval** | 50-500 (advanced) | Strike grid spacing |
| **Risk-Free Rate** | 0-10% (advanced) | Greece calculations |
| **Implied Volatility** | 5-100% (advanced) | Market vol assumption |

---

## 🔌 Integration Points

### Current State (Mock Data)
The dashboard currently uses **mock data** for demo purposes:
- ✅ Price charts generated with realistic randomness
- ✅ Volume data with realistic anomalies
- ✅ Pattern detection on mock OHLCV data
- ✅ Greeks calculations with configurable IV

### Production Integration (Next Steps)

#### Step 1: Connect Analytics Modules
Replace `generate_mock_market_data()` with live feeds:

```python
# Current (mock):
market_data = generate_mock_market_data(instrument, timeframe, periods=100)

# Production (live API):
market_data = dhan_api.fetch_intraday_options(
    instrument=instrument,
    interval=timeframe.lower()
)
```

#### Step 2: Integrate DHAN Broker API
```python
# In Section 6 (Trade Recommendation):
if st.button("✅ Confirm Trade Setup"):
    from analytics.dhan_integration import DhanClient
    
    dhan = DhanClient(api_key=os.getenv("DHAN_API_KEY"))
    order = dhan.place_order(
        symbol=selected_strike,
        side="BUY",
        quantity=1,
        price=greeks_call['premium']
    )
    st.success(f"Order placed: {order['order_id']}")
```

#### Step 3: Real-Time WebSocket Updates
```python
# In Sidebar:
from analytics.dhan_websocket import DhanWebSocket

ws = DhanWebSocket(on_data_callback=update_dashboard)
ws.subscribe(instrument, expiry_date)
```

---

## 📊 Data Flow Diagram

```
┌─────────────────────────────────────────────────────┐
│            DHAN Broker API (Live Data)             │
│  • Real-time options chain                         │
│  • Bid-ask spreads                                 │
│  • Open Interest & Greeks                          │
└────────────────┬────────────────────────────────────┘
                 │
    ┌────────────┴────────────┐
    ▼                         ▼
┌─────────────────────┐  ┌──────────────────────┐
│  Price & Pattern    │  │  News & Sentiment    │
│  Detection          │  │  Analysis            │
│  • Candlesticks     │  │  • NewsAPI           │
│  • Bollinger Bands  │  │  • TextBlob NLP      │
│  • Volume Trends    │  │  • Market Drivers    │
└────────┬────────────┘  └──────────┬───────────┘
         │                          │
    ┌────┴──────────────────────────┴────┐
    │                                    │
    ▼                                    ▼
┌──────────────────┐        ┌─────────────────────┐
│  ML Prediction   │        │  Greeks Calc        │
│  (RandomForest)  │        │  (Black-Scholes)    │
│  • Direction     │        │  • Delta, Gamma     │
│  • Confidence    │        │  • Theta, Vega, Rho │
└────────┬─────────┘        └──────────┬──────────┘
         │                             │
         └────────────────┬────────────┘
                          ▼
            ┌──────────────────────────┐
            │  Trade Recommendation    │
            │  Engine                  │
            │  • Risk/Reward Analysis  │
            │  • Strike Selection      │
            │  • Position Sizing       │
            └────────────┬─────────────┘
                         ▼
            ┌──────────────────────────┐
            │  Streamlit Dashboard     │
            │  • Visualization         │
            │  • Trade Execution       │
            │  • Backtest Results      │
            └──────────────────────────┘
```

---

## 🔧 Troubleshooting

### Issue: "Failed to import analytics modules"
**Solution**: Ensure analytics files are in `/analytics/` directory
```bash
ls -la analytics/
# Should show: __init__.py, predictor.py, greeks.py, sentiment.py, etc.
```

### Issue: Charts not displaying
**Solution**: Upgrade Plotly
```bash
pip install --upgrade plotly
```

### Issue: Slow performance
**Solution**: Reduce mock data periods in `generate_mock_market_data()`
```python
market_data = generate_mock_market_data(instrument, timeframe, periods=50)  # Was 100
```

### Issue: API timeouts
**Solution**: Add timeout & retry logic (when integrated with live APIs)
```python
@st.cache_resource
def get_market_data_cached():
    return market_data  # Cache to avoid repeated API calls
```

---

## 📈 Performance Benchmarks

| Component | Metric | Target |
|-----------|--------|--------|
| Dashboard Load | Time to interactive | < 5 seconds |
| Chart Rendering | Candlestick + indicators | < 2 seconds |
| Greeks Calculation | 100 strikes | < 500ms |
| Sentiment Update | API call + scoring | < 3 seconds |
| Volume Analysis | 1000+ data points | < 100ms |

---

## 🎯 Advanced Usage

### Custom Indicator: Add RSI Overlay
```python
# In "Real-Time Price & Pattern Analysis" section:
rsi = calculate_rsi(market_data['Close'], period=14)
fig.add_trace(go.Scatter(
    x=market_data['DateTime'],
    y=rsi,
    name='RSI 14',
    secondary_y=True
))
```

### Multi-Instrument Comparison
```python
instruments = ["NIFTY", "SENSEX", "BANKNIFTY"]
for inst in instruments:
    data = generate_mock_market_data(inst, timeframe)
    st.write(f"**{inst}**: {data['Close'].iloc[-1]:.2f}")
```

### Export Trade Setup to Excel
```python
import openpyxl

if st.button("📥 Export Trade Setup"):
    trade_df = pd.DataFrame({
        'Instrument': [instrument],
        'Strike': [selected_strike],
        'Premium': [greeks_call['premium']],
        'Delta': [greeks_call['delta']],
        'Expiry': [expiry_date]
    })
    
    trade_df.to_csv('trade_setup.csv', index=False)
    st.success("✅ Trade setup exported to trade_setup.csv")
```

---

## 📚 Related Documentation

- **Analytics Validation Report**: [VALIDATION_REPORT.md](VALIDATION_REPORT.md)
- **India Options Skill**: [.github/skills/india-options-prediction/SKILL.md](.github/skills/india-options-prediction/SKILL.md)
- **Specialist Agent Guide**: [.github/agents/india-options-specialist.agent.md](.github/agents/india-options-specialist.agent.md)
- **Code Standards**: [.github/instructions/india-options.instructions.md](.github/instructions/india-options.instructions.md)

---

## 🚀 Next Steps

1. **✅ Dashboard created** — Ready to run
2. **⏳ Connect live data** — Replace mock with DHAN API
3. **⏳ Enable trade execution** — Add DHAN order placement
4. **⏳ Real-time updates** — Implement WebSocket feed
5. **⏳ Historical backtesting** — Validate strategy performance

---

## 📞 Support

For issues or feature requests:
1. Check [VALIDATION_REPORT.md](VALIDATION_REPORT.md) for code standards
2. Review analytics modules for integration points
3. Ask the **india-options-specialist agent** for debugging help
4. Use the **india-options-prediction skill** for workflow guidance

---

**Dashboard Version**: 1.0  
**Last Updated**: May 13, 2026  
**Status**: Ready for testing ✅
