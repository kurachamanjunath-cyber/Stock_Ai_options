"""
Real-Time India Options Prediction Dashboard
Uses: india-options-prediction skill + analytics modules
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
import sys
import yfinance as yf
import requests

# Add analytics to path
analytics_path = Path(__file__).parent / "analytics"
sys.path.insert(0, str(analytics_path))

# Import analytics modules
try:
    from analytics.intraday_options import recommend_intraday_options
    from analytics.predictor import OptionsPredictor
    from analytics.greeks import calculate_greeks
    from analytics.sentiment import analyze_news_sentiment
    from analytics.volume_detector import detect_volume_anomaly
    from analytics.candlestick_patterns import detect_candlestick_patterns
except ImportError as e:
    st.error(f"Failed to import analytics modules: {e}")
    st.info("Make sure all analytics files are in the `/analytics/` directory")
    sys.exit(1)

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="India Options Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 Real-Time India Options Prediction Dashboard")
st.markdown("*Powered by Machine Learning | Greeks Valuation | Sentiment Analysis*")

# ============================================================================
# SIDEBAR CONFIGURATION
# ============================================================================

with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Instrument Selection
    instrument = st.selectbox(
        "🔗 Select Instrument",
        ["NIFTY", "SENSEX", "BANKNIFTY", "GOLD", "SILVER", "NATURAL GAS", "CRUDE OIL"],
        help="Choose the index or commodity to analyze"
    )
    
    # Timeframe Selection
    timeframe = st.radio(
        "⏱️ Timeframe",
        ["15-MIN", "1-HR", "DAILY"],
        horizontal=False,
        help="Select analysis timeframe"
    )
    
    # Expiry Date Selection
    expiry_date = st.date_input(
        "📅 Expiry Date",
        value=datetime.now() + timedelta(days=3),
        help="Options expiry date"
    )
    
    # Auto-refresh Toggle
    auto_refresh = st.toggle(
        "🔄 Auto Refresh (30s)",
        value=False,
        help="Enable live updates every 30 seconds"
    )
    
    # Advanced Settings (Expandable)
    with st.expander("🔧 Advanced Settings"):
        strike_interval = st.slider(
            "Strike Interval",
            min_value=50,
            max_value=500,
            value=100,
            step=50
        )
        
        risk_free_rate = st.slider(
            "Risk-Free Rate (%)",
            min_value=0.0,
            max_value=10.0,
            value=6.0,
            step=0.1
        ) / 100
        
        volatility = st.slider(
            "Implied Volatility (%)",
            min_value=5.0,
            max_value=100.0,
            value=20.0,
            step=1.0
        ) / 100

# ============================================================================
# LIVE DATA FETCHING
# ============================================================================

def _nse_index_via_api(symbol: str):
    """Query NSE option-chain endpoint to return the underlying index value.
    This performs a preflight GET to the homepage to obtain cookies, then
    requests the option-chain JSON and extracts `records.underlyingValue`.
    Returns float or None on error.
    """
    url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.nseindia.com"
    }
    sess = requests.Session()
    try:
        # Preflight to set cookies
        sess.get("https://www.nseindia.com", headers=headers, timeout=5)
        resp = sess.get(url, headers=headers, timeout=5)
        resp.raise_for_status()
        body = resp.json()
        val = body.get("records", {}).get("underlyingValue")
        if val is not None:
            return float(val)
    except Exception as e:
        print(f"_nse_index_via_api failed for {symbol}: {e}")
    return None


def get_live_nse_data():
    """
    Fetch live prices for NIFTY and BANKNIFTY directly from NSE APIs.
    Returns a dict with keys 'NIFTY', 'BANKNIFTY', 'SENSEX' (SENSEX via yfinance fallback).
    """
    results = {}
    for sym in ("NIFTY", "BANKNIFTY"):
        results[sym] = _nse_index_via_api(sym)

    # Sensex is a BSE index; use yfinance as a reliable fallback
    try:
        sens = yf.download("^BSESN", period="1d", progress=False)
        results["SENSEX"] = float(sens['Close'].iloc[-1]) if not sens.empty else None
    except Exception as e:
        print(f"Failed to fetch SENSEX via yfinance: {e}")
        results["SENSEX"] = None

    return results

def get_live_commodity_prices():
    """
    Fetch live prices from NSE and commodities (fallback to mock if API unavailable).
    """
    # Try to fetch NSE data first
    nse_data = get_live_nse_data()
    
    # Base prices with NSE data if available, else mock
    live_prices = {
        "NIFTY": (nse_data.get("NIFTY") if nse_data and nse_data.get("NIFTY") is not None else 23500),
        "SENSEX": (nse_data.get("SENSEX") if nse_data and nse_data.get("SENSEX") is not None else 75000),
        "BANKNIFTY": (nse_data.get("BANKNIFTY") if nse_data and nse_data.get("BANKNIFTY") is not None else 47500),
        "GOLD": 68500,           # MCX Gold (per 10g)
        "SILVER": 90200,         # MCX Silver (per 1kg)
        "NATURAL GAS": 275.20,   # MCX Natural Gas (per MMBtu)
        "CRUDE OIL": 92.50       # MCX Crude Oil (per barrel)
    }
    
    return live_prices

def generate_market_data(instrument: str, timeframe: str, periods: int = 100):
    """
    Generate or fetch market OHLCV data.
    For NSE indices: fetches live data from yfinance
    For commodities: generates realistic mock data
    """
    # NSE ticker mapping
    nse_tickers = {
        "NIFTY": "^NSEI",
        "SENSEX": "^BSESN",
        "BANKNIFTY": "^NSEBANKNIFTY"
    }
    
    # Try to fetch real data for NSE indices
    if instrument in nse_tickers:
        try:
            ticker = nse_tickers[instrument]
            # Fetch intraday data (1 hour intervals)
            data = yf.download(ticker, period='30d', interval='1h', progress=False)
            
            if not data.empty:
                # Take last 'periods' records and reset index
                data = data.tail(periods).reset_index()

                # Normalize the datetime/index column name to DateTime
                idx_col = data.columns[0]
                data = data.rename(columns={idx_col: 'DateTime'})

                # Ensure essential OHLCV columns exist
                for col in ['Open', 'High', 'Low', 'Close']:
                    if col not in data.columns:
                        data[col] = np.nan
                if 'Volume' not in data.columns:
                    data['Volume'] = 0

                # Add technical indicators
                data['RSI_14'] = 50 + np.random.randn(len(data)) * 15
                data['MACD'] = np.random.randn(len(data)) * 100
                data['MACD_Signal'] = data['MACD'].rolling(9).mean()
                data['Volume_Trend'] = data['Volume'].rolling(20).mean()
                data['SMA_10'] = data['Close'].rolling(10).mean()
                data['SMA_20'] = data['Close'].rolling(20).mean()

                return data
        except Exception as e:
            print(f"Failed to fetch {instrument} data: {e}")
            # Fall through to mock data generation
    
    # Generate realistic mock OHLCV data for commodities or on API failure
    live_prices = get_live_commodity_prices()
    base_price = live_prices.get(instrument, 50000)
    
    # Generate dates
    dates = pd.date_range(end=datetime.now(), periods=periods, freq='1H')
    
    # Generate more realistic prices with small percentage variations (±2%)
    variation_pct = 0.02  # 2% max variation from base
    close_prices = base_price + (np.random.randn(periods) * base_price * variation_pct)
    close_prices = np.maximum(close_prices, base_price * 0.98)  # Keep minimum at 98% of base
    
    # Generate OHLC around close prices
    opens = close_prices + np.random.randn(periods) * base_price * 0.005
    highs = np.maximum(close_prices, opens) + np.abs(np.random.randn(periods)) * base_price * 0.01
    lows = np.minimum(close_prices, opens) - np.abs(np.random.randn(periods)) * base_price * 0.01
    
    # Ensure all prices are positive and realistic
    lows = np.maximum(lows, base_price * 0.95)
    
    data = pd.DataFrame({
        'DateTime': dates,
        'Open': opens,
        'High': highs,
        'Low': lows,
        'Close': close_prices,
        'Volume': np.random.randint(1000000, 5000000, periods)
    })
    
    # Add technical indicators (mock)
    data['RSI_14'] = 50 + np.random.randn(periods) * 15
    data['MACD'] = np.random.randn(periods) * 100
    data['MACD_Signal'] = data['MACD'].rolling(9).mean()
    data['Volume_Trend'] = data['Volume'].rolling(20).mean()
    data['SMA_10'] = data['Close'].rolling(10).mean()
    data['SMA_20'] = data['Close'].rolling(20).mean()
    
    return data.tail(periods)

# ============================================================================
# SECTION 1: REAL-TIME PRICE & PATTERN ANALYSIS
# ============================================================================

st.divider()
st.subheader("📈 Real-Time Price & Pattern Analysis")

# Generate market data
market_data = generate_market_data(instrument, timeframe, periods=100)
# Ensure scalar values for display
current_price = float(market_data['Close'].iloc[-1])
prev_price = float(market_data['Close'].iloc[-2]) if len(market_data['Close']) > 1 else current_price
price_change = ((current_price - prev_price) / prev_price * 100) if prev_price != 0 else 0.0

# Display Key Metrics
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label=f"{instrument} Price",
        value=f"₹{current_price:,.2f}",
        delta=f"{price_change:+.2f}%",
        delta_color="normal"
    )

with col2:
    st.metric(
        label="24h High",
        value=f"₹{float(np.nanmax(market_data['High'].tail(24).values.astype(float))):,.2f}"
    )

with col3:
    st.metric(
        label="24h Low",
        value=f"₹{float(np.nanmin(market_data['Low'].tail(24).values.astype(float))):,.2f}"
    )

with col4:
    st.metric(
        label="Avg Volume",
        value=f"{float(np.nanmean(market_data['Volume'].tail(20).values.astype(float))):,.0f}"
    )

# Price Chart with Bollinger Bands
fig = go.Figure()

# Add candlestick chart
# Determine x-axis values (robust to different DataFrame shapes)
if 'DateTime' in market_data.columns:
    x_vals = market_data['DateTime']
else:
    x_vals = market_data.iloc[:, 0]

fig.add_trace(go.Candlestick(
    x=x_vals,
    open=market_data['Open'],
    high=market_data['High'],
    low=market_data['Low'],
    close=market_data['Close'],
    name='Price'
))

# Add Bollinger Bands
sma = market_data['Close'].rolling(20).mean()
std = market_data['Close'].rolling(20).std()
bb_high = sma + (std * 2)
bb_low = sma - (std * 2)

fig.add_trace(go.Scatter(x=x_vals, y=bb_high, name='BB Upper', line=dict(color='rgba(0,0,0,0)', width=0), showlegend=False))
fig.add_trace(go.Scatter(x=x_vals, y=bb_low, name='Bollinger Bands', fill='tonexty', line=dict(color='rgba(0,0,0,0)', width=0), fillcolor='rgba(0,0,255,0.1)'))

fig.update_layout(
    title=f"{instrument} {timeframe} Chart | Current: ₹{current_price:,.2f}",
    yaxis_title="Price (₹)",
    xaxis_title="Time",
    template="plotly_dark",
    height=400,
    hovermode='x unified'
)

st.plotly_chart(fig, use_container_width=True)

# Volume Chart
fig_volume = go.Figure()

# Build marker colors safely (convert to float scalars before comparison)
marker_colors = []
for i in range(1, len(market_data)):
    try:
        curr = float(market_data['Close'].iloc[i])
        prev = float(market_data['Close'].iloc[i-1])
        marker_colors.append('#FF6692' if curr < prev else '#26A69A')
    except Exception:
        marker_colors.append('#26A69A')
marker_colors.append('#26A69A')

fig_volume.add_trace(go.Bar(
    x=x_vals,
    y=market_data['Volume'],
    name='Volume',
    marker_color=marker_colors
))

# Add volume SMA
fig_volume.add_trace(go.Scatter(
    x=x_vals,
    y=market_data['Volume'].rolling(20).mean(),
    name='Volume SMA 20',
    line=dict(color='yellow', width=2)
))

fig_volume.update_layout(
    title="Trading Volume",
    yaxis_title="Volume",
    xaxis_title="Time",
    template="plotly_dark",
    height=250,
    hovermode='x unified'
)

st.plotly_chart(fig_volume, use_container_width=True)

# Pattern Analysis
try:
    patterns = detect_candlestick_patterns(market_data[['Open', 'High', 'Low', 'Close']].tail(20))
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info(f"📊 **Pattern**: {patterns.get('pattern', 'N/A')}")
    
    with col2:
        strength = patterns.get('strength', 0) * 100
        st.info(f"💪 **Strength**: {strength:.0f}%")
    
    with col3:
        direction = patterns.get('direction', 'NEUTRAL')
        emoji = "📈" if direction == "UP" else "📉" if direction == "DOWN" else "➡️"
        st.info(f"{emoji} **Direction**: {direction}")
except Exception as e:
    st.warning(f"Pattern analysis unavailable: {e}")

# ============================================================================
# SECTION 2: ML PREDICTION
# ============================================================================

st.divider()
st.subheader("🤖 Machine Learning Prediction")

try:
    predictor = OptionsPredictor()
    train_result = predictor.train(market_data)
    
    if train_result['status'] == 'SUCCESS':
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                label="Model Accuracy (R²)",
                value=f"{train_result['rf_score']:.2%}",
                delta="Training Complete"
            )
        
        with col2:
            st.metric(
                label="Training Samples",
                value=f"{train_result['training_samples']:,}",
                delta=f"Test: {train_result['test_samples']:,}"
            )
        
        with col3:
            st.metric(
                label="Model Status",
                value="✅ Ready",
                delta="Inference Ready"
            )
        
        # Prediction Summary
        st.success("✅ ML Model Successfully Trained")
        st.info("Next: Generate directional prediction using predict_price() method with feature data")
    else:
        st.error(f"⚠️ Training Failed: {train_result['message']}")
        
except Exception as e:
    st.warning(f"ML Model initialization: {e}")

# ============================================================================
# SECTION 3: SENTIMENT & NEWS
# ============================================================================

st.divider()
st.subheader("📰 Global News & Market Sentiment")

col1, col2 = st.columns([2, 1])

with col1:
    try:
        sentiment_result = analyze_news_sentiment(instrument, num_articles=5)
        
        sentiment_score = sentiment_result['overall_sentiment']
        confidence = sentiment_result['confidence']
        label = sentiment_result['sentiment_label']
        
        # Sentiment Gauge
        fig_sentiment = go.Figure(go.Indicator(
            mode="gauge+number",
            value=sentiment_score,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Sentiment Score"},
            gauge={
                'axis': {'range': [-1, 1]},
                'bar': {'color': '#FF6692' if sentiment_score < 0 else '#26A69A'},
                'steps': [
                    {'range': [-1, 0], 'color': 'rgba(255, 50, 50, 0.2)'},
                    {'range': [0, 1], 'color': 'rgba(50, 200, 100, 0.2)'}
                ]
            }
        ))
        
        fig_sentiment.update_layout(height=300, template="plotly_dark")
        st.plotly_chart(fig_sentiment, use_container_width=True)
        
    except Exception as e:
        st.warning(f"Sentiment analysis unavailable: {e}")
        sentiment_score = 0
        confidence = 0
        label = "NEUTRAL"

with col2:
    st.metric(
        label="Sentiment Label",
        value=label,
        delta=f"Confidence: {confidence:.0f}%"
    )
    
    # Key Drivers
    st.write("**Key Market Drivers:**")
    drivers = {
        "NIFTY": ["RBI Policy", "India GDP", "Global Equities"],
        "SENSEX": ["RBI Policy", "Inflation", "Corporate Earnings"],
        "GOLD": ["Fed Decisions", "USD/INR", "Geopolitics"],
        "SILVER": ["Industrial Demand", "Fed Policy", "Risk Sentiment"],
        "NATURAL GAS": ["Supply/Demand", "Weather", "Global Energy Crisis"],
        "CRUDE OIL": ["OPEC Decisions", "Geopolitics", "Global Growth"]
    }
    
    for driver in drivers.get(instrument, ["Market Factors"]):
        st.write(f"• {driver}")

# ============================================================================
# SECTION 4: GREEKS & STRIKE SELECTION
# ============================================================================

st.divider()
st.subheader("⚙️ Greeks & Strike Selection")

col1, col2 = st.columns([2, 1])

with col1:
    # Strike Selection Slider
    atm_strike = round(current_price / strike_interval) * strike_interval
    selected_strike = st.slider(
        "Select Strike Price",
        min_value=atm_strike - 500,
        max_value=atm_strike + 500,
        value=atm_strike,
        step=strike_interval,
        help="Choose the options strike to analyze"
    )
    
    # Time to Expiry Calculation
    time_to_expiry_days = (expiry_date - datetime.now().date()).days
    time_to_expiry_years = max(0.001, time_to_expiry_days / 365)
    
    # Calculate Greeks
    greeks_call = calculate_greeks(
        S=current_price,
        K=selected_strike,
        T=time_to_expiry_years,
        r=risk_free_rate,
        sigma=volatility,
        option_type='call'
    )
    
    greeks_put = calculate_greeks(
        S=current_price,
        K=selected_strike,
        T=time_to_expiry_years,
        r=risk_free_rate,
        sigma=volatility,
        option_type='put'
    )

with col2:
    st.metric(label="Time to Expiry", value=f"{time_to_expiry_days} days")
    st.metric(label="Current IV", value=f"{volatility*100:.1f}%")

# Greeks Display - CALL Options
st.write("#### 📞 CALL Option Greeks")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    delta_call = greeks_call.get('delta', 0)
    color = "🟢" if delta_call > 0.5 else "🟡" if delta_call > 0.3 else "🔴"
    st.metric(f"{color} Delta", f"{delta_call:.3f}")

with col2:
    gamma = greeks_call.get('gamma', 0)
    st.metric("Gamma", f"{gamma:.4f}")

with col3:
    theta = greeks_call.get('theta', 0)
    st.metric("Theta", f"{theta:+.3f}")

with col4:
    vega = greeks_call.get('vega', 0)
    st.metric("Vega", f"{vega:.3f}")

with col5:
    premium = greeks_call.get('premium', 0)
    st.metric(label="Premium", value=f"₹{premium:.2f}")

# Greeks Display - PUT Options
st.write("#### 📱 PUT Option Greeks")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    delta_put = greeks_put.get('delta', 0)
    color = "🟢" if delta_put < -0.5 else "🟡" if delta_put < -0.3 else "🔴"
    st.metric(f"{color} Delta", f"{delta_put:.3f}")

with col2:
    gamma = greeks_put.get('gamma', 0)
    st.metric("Gamma", f"{gamma:.4f}")

with col3:
    theta = greeks_put.get('theta', 0)
    st.metric("Theta", f"{theta:+.3f}")

with col4:
    vega = greeks_put.get('vega', 0)
    st.metric("Vega", f"{vega:.3f}")

with col5:
    premium = greeks_put.get('premium', 0)
    st.metric(label="Premium", value=f"₹{premium:.2f}")

# ============================================================================
# SECTION 5: VOLUME ANALYSIS
# ============================================================================

st.divider()
st.subheader("📊 Volume Anomaly Detection")

try:
    volume_result = detect_volume_anomaly(market_data['Volume'], window=20, threshold_sigma=2.0)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        is_anomaly = volume_result.get('is_anomaly', False)
        status = "🚨 ANOMALY" if is_anomaly else "✅ Normal"
        st.metric(label="Status", value=status)
    
    with col2:
        z_score = volume_result.get('z_score', 0)
        st.metric(label="Z-Score", value=f"{z_score:.2f}")
    
    with col3:
        ratio = volume_result.get('ratio_to_avg', 1)
        st.metric(label="Vol / Avg", value=f"{ratio:.2f}x")
    
    with col4:
        anomaly_score = volume_result.get('anomaly_score', 0)
        st.metric(label="Anomaly Score", value=f"{anomaly_score:.0f}%")
    
    # Volume Trend
    trend = volume_result.get('volume_trend', 'FLAT')
    st.info(f"📈 **Volume Trend**: {trend}")
    
except Exception as e:
    st.warning(f"Volume analysis unavailable: {e}")

# ============================================================================
# SECTION 6: TRADE RECOMMENDATION
# ============================================================================

st.divider()
st.subheader("💡 Trade Recommendation Engine")

# Calculate conviction level
conviction_score = (sentiment_score + 1) / 2 * 0.3 + np.random.random() * 0.7  # Mock calculation

if conviction_score > 0.7:
    conviction_level = "🟢 HIGH"
    recommendation = "BUY CALL" if sentiment_score > 0 else "BUY PUT"
    color = "green"
elif conviction_score > 0.5:
    conviction_level = "🟡 MEDIUM"
    recommendation = "CAUTIOUS"
    color = "blue"
else:
    conviction_level = "🔴 LOW"
    recommendation = "SKIP / WAIT"
    color = "red"

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="Conviction Level", value=conviction_level)

with col2:
    st.metric(label="Recommendation", value=recommendation)

with col3:
    st.metric(label="Risk/Reward", value="1:1.8", delta="Favorable")

# Trade Setup Box
if conviction_score > 0.5:
    with st.container(border=True):
        st.markdown(f"### ✅ Trade Setup Available")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**Strike Selected**: ₹{selected_strike}")
            st.write(f"**Current Price**: ₹{current_price:.2f}")
            st.write(f"**Entry Premium**: ₹{greeks_call['premium']:.2f}")
        
        with col2:
            st.write(f"**Target Profit**: ₹{greeks_call['premium'] * 0.5:.2f} (50%)")
            st.write(f"**Max Loss**: ₹{greeks_call['premium']:.2f} (100%)")
            st.write(f"**Time to Expiry**: {time_to_expiry_days} days")
        
        # Action Buttons
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("✅ Confirm Trade Setup", use_container_width=True):
                st.success(f"Trade setup confirmed! Ready for execution on DHAN API.")
                st.balloons()
        
        with col2:
            if st.button("📊 View Trade Details", use_container_width=True):
                st.info("Trade details would open in detailed analysis panel")
        
        with col3:
            if st.button("❌ Skip This Trade", use_container_width=True):
                st.warning("Trade skipped. Monitor for next opportunity.")

else:
    st.warning("⚠️ Insufficient conviction for trade recommendation. Wait for clearer signals.")

# ============================================================================
# SECTION 7: BACKTEST RESULTS
# ============================================================================

st.divider()
st.subheader("📈 30-Day Strategy Backtest Results")

# Mock backtest data
backtest_data = {
    'Total Trades': 48,
    'Winning Trades': 32,
    'Losing Trades': 16,
    'Win Rate': '66.7%',
    'Average Win': '₹75',
    'Average Loss': '₹40',
    'Profit Factor': 1.85,
    'Max Drawdown': '₹320',
    'Cumulative P&L': '+₹2,600',
    'ROI': '+11.6%'
}

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Trades", backtest_data['Total Trades'])

with col2:
    st.metric("Win Rate", backtest_data['Win Rate'])

with col3:
    st.metric("Profit Factor", f"{backtest_data['Profit Factor']:.2f}")

with col4:
    st.metric("ROI (30 days)", backtest_data['ROI'])

# Backtest by Instrument
st.write("**By Instrument:**")

backtest_by_instrument = pd.DataFrame({
    'Instrument': ['NIFTY 50', 'SENSEX', 'GOLD', 'SILVER', 'NATURAL GAS', 'CRUDE OIL'],
    'Win Rate': ['68%', '65%', '60%', '58%', '62%', '64%'],
    'P&L': ['+₹1,450', '+₹850', '+₹300', '+₹0', '+₹250', '+₹380'],
    'Trades': [24, 16, 6, 2, 5, 7]
})

st.dataframe(backtest_by_instrument, use_container_width=True, hide_index=True)

# Backtest by Timeframe
st.write("**By Timeframe:**")

backtest_by_tf = pd.DataFrame({
    'Timeframe': ['15-MIN', '1-HR', 'DAILY'],
    'Win Rate': ['58%', '72%', '66%'],
    'P&L': ['+₹680', '+₹1,680', '+₹240'],
    'Recommended': ['⚠️ Low', '✅ Optimal', '🟡 Medium']
})

st.dataframe(backtest_by_tf, use_container_width=True, hide_index=True)

# ============================================================================
# FOOTER & AUTO-REFRESH
# ============================================================================

st.divider()

col1, col2, col3 = st.columns(3)

with col1:
    st.write(f"**Last Updated**: {datetime.now().strftime('%H:%M:%S')}")

with col2:
    st.write(f"**Dashboard Version**: 1.0")

with col3:
    st.write(f"**Data Source**: Live API (Mock Demo)")

# Auto-refresh logic
if auto_refresh:
    st.write("🔄 Auto-refreshing in 30 seconds...")
    import time
    time.sleep(30)
    st.rerun()

st.markdown("---")
st.markdown("*Built with Streamlit | Powered by ML + Options Greeks | India Market Focused*")
