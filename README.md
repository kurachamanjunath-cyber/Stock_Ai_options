# Advanced INTRADAY Options Predictor

A Python application with a Streamlit UI for real-time intraday options trading signals for MCX commodities, NSE indices (NIFTY, SENSEX), and global futures.

## Features

### 🎯 Core Features
- **Real-time Intraday Options Signals** - BUY CALL / BUY PUT / WAIT signals based on candlestick patterns
- **Support & Resistance Levels** - Automatically calculated intraday trading levels
- **Multi-Factor Analysis** - Combines price action, technical indicators, volume, and sentiment
- **Live Greeks Calculation** - Options premium estimation using Black-Scholes model
- **Candlestick Pattern Detection** - Recognizes 30+ patterns for trade setup confirmation
- **🚀 Dhan WebSocket Integration** - Real-time sub-second price updates

### 📊 Supported Assets
- **MCX Commodities**: Gold, Silver, Crude Oil, Natural Gas, Copper, Zinc, Lead
- **NSE Indices**: NIFTY 50, SENSEX, BANK NIFTY
- **Global Futures**: Gold, Crude Oil, Silver, Natural Gas (futures)

### 🔄 Data & Analysis
- Technical indicators: RSI, MACD, Bollinger Bands, ATR, Moving Averages
- Volume trend and anomaly detection
- News sentiment analysis
- Intraday price targets and breakeven levels
- **Real-time WebSocket streaming** (with Dhan API)

## Installation

### 1. Basic Setup (with approximated data)

```bash
# Install dependencies
python3 -m pip install -r requirements.txt

# Run the app
streamlit run app.py
```

> If installation fails on macOS with Xcode tools error, run: `xcode-select --install`

### 2. Advanced Setup (with Live Dhan WebSocket - Recommended) ⭐

For **real-time MCX and NSE options data with sub-second updates**:

#### Step 1: Get Dhan Account & API Credentials
1. Sign up at [Dhan Trading](https://dhanhq.com)
2. Complete KYC verification
3. Get your **API Key** and **Client ID** from dashboard
4. Enable API access in settings

#### Step 2: Install WebSocket Dependencies
```bash
pip install websocket-client python-dotenv
```

#### Step 3: Configure Environment
Create a `.env` file in the project root:
```
DHAN_API_KEY=your_api_key_here
DHAN_CLIENT_ID=your_client_id_here
```

#### Step 4: Start the App
```bash
streamlit run app.py
```

The app will automatically connect to Dhan WebSocket on startup! ✅

## Usage

### 1. Launch the App
```bash
streamlit run app.py
```

**Check the sidebar** - You'll see the connection status:
- ✅ **WebSocket Connected** - Real-time data active
- ⚠️ **WebSocket Offline** - Using yfinance (fallback)

### 2. Select Asset in Sidebar
- Choose category: MCX Commodities, NSE Indices, or Global Futures
- Select specific asset (e.g., NIFTY 50, MCX Gold)
- Adjust strike interval and other parameters
- App automatically subscribes to live data if WebSocket is connected

### 3. Review Signals
- **Tab 1 (OPTIONS SIGNAL)**: Main intraday recommendation
  - Signal: BUY CALL / BUY PUT / WAIT
  - Entry/Target/Stop Loss levels (from support/resistance)
  - Confidence score and pattern strength
  
- **Tab 2 (Price & Volume)**: Price action and volume analysis
- **Tab 3 (Technical)**: RSI, MACD, and other indicators
- **Tab 4 (Sentiment)**: News sentiment analysis
- **Tab 5 (INTRADAY OPTIONS)**: Specific call/put recommendations with strikes
- **Tab 6 (Setup)**: WebSocket configuration and troubleshooting

### 4. Monitor Levels
- Support and resistance displayed on main chart
- Intraday targets shown for reference
- Greeks calculations for option premium guidance
- All prices update in real-time (if WebSocket connected)

## Data Sources

### Without WebSocket (Default - yfinance)
- MCX Commodities: Global futures + conversion to INR
- NIFTY/SENSEX: Yahoo Finance
- Option Premiums: Estimated via Greeks model
- Updates: 5-15 minutes delayed

### With Dhan WebSocket (Recommended) ⭐
- MCX Commodities: ✅ Live MCX exchange data (real-time)
- NIFTY/SENSEX: ✅ Live NSE/BSE exchange data (real-time)
- Option Chains: ✅ Real option premiums and Greeks
- Updates: ✅ Sub-second real-time (0-1 sec latency)
- Connection: ✅ Auto-connects on app startup
- Data Freshness: ✅ Market hours continuous streaming

## File Structure

```
Stock_Ai_options/
├── app.py                             # Main Streamlit application
├── requirements.txt                   # Python dependencies
├── .env                              # Environment variables (create this)
│
└── analytics/
    ├── __init__.py
    ├── greeks.py                     # Black-Scholes Greeks calculations
    ├── predictor.py                  # ML-based price prediction
    ├── sentiment.py                  # News sentiment analysis
    ├── volume_detector.py            # Volume anomaly detection
    ├── candlestick_patterns.py       # Pattern recognition
    ├── intraday_options.py           # Intraday trade recommendations
    ├── dhan_integration.py           # Dhan REST API client
    └── dhan_websocket.py             # Dhan WebSocket streaming (NEW)
```

## Trading Tips

### ✅ When to Trade
- Strong candlestick pattern (confidence > 70%)
- Multi-factor score aligned with price direction
- Volume support for the trade

### ❌ When to Wait
- Mixed signals (confidence < 50%)
- No clear pattern or setup
- During market consolidation

### ⚠️ Risk Management
- Always set stop loss at support/resistance
- Use ATM or slightly OTM strikes for better probability
- Exit at 50% profit or at target level
- Same-day exit recommended for intraday trades

## Performance & Testing

### Run Syntax Check
```bash
python3 -m py_compile app.py analytics/dhan_integration.py
```

### Test with Different Assets
- Try different commodities (gold, silver, crude)
- Test indices (NIFTY, SENSEX)
- Compare signals with actual market data

## VS Code Integration

Use the built-in task: **"Run Streamlit App"** to launch instantly.

## Limitations & Disclaimers

- ⚠️ **Not Financial Advice** - Educational tool only
- 📊 **Backtesting Recommended** - Test signals on historical data first
- 🔄 **Data Accuracy** - yfinance data may have delays; use Dhan API for live data
- 📱 **Intraday Focus** - Designed for same-day trading only
- 💼 **Professional Advice** - Consult financial advisor before trading

## Roadmap

- [ ] Dhan API integration for live data (in progress)
- [ ] Historical performance tracking
- [ ] Advanced Greeks visualization
- [ ] Multi-leg strategy recommendations
- [ ] Trade journal and P&L tracking
- [ ] Mobile app version

## Support

For issues or questions:
1. Check the README
2. Review tab 6 (Analysis Details) in the app for setup help
3. Ensure all dependencies are installed: `pip install -r requirements.txt`
4. Verify Dhan API credentials if using live data

---

**Last Updated**: May 2026
**Version**: 2.0 - Intraday Focus Edition
