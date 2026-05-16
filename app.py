import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import ta
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Tuple
import time
import warnings
warnings.filterwarnings('ignore')

# Import analytics modules
try:
    from analytics.greeks import calculate_greeks, estimate_atm_strike, calculate_breakeven_points
    from analytics.sentiment import analyze_news_sentiment, sentiment_to_signal
    from analytics.volume_detector import detect_volume_anomaly
    from analytics.predictor import predict_options_entry_target, calculate_multi_factor_score
    from analytics.candlestick_patterns import detect_candlestick_patterns, calculate_support_resistance
    from analytics.intraday_options import recommend_intraday_options, get_intraday_price_targets
    from analytics.mcx_live import get_live_mcx_quote
    from analytics.live_nse import get_live_nse_quote
    from analytics.live_global import get_live_global_quote
    from analytics.target_price_forecast import FORECAST_INTERVALS, build_target_price_forecast
except ImportError as e:
    st.error(f"Analytics module error: {e}. Please ensure all files in analytics/ directory are created.")
    st.stop()

st.set_page_config(page_title="Advanced Intraday Options Predictor", layout="wide")

# ============ CONFIGURATION ============

st.title("📊 Advanced INTRADAY Options Predictor")
st.markdown("**INTRADAY CALL/PUT Signals → Today's Entry & Target Prices for MCX Commodities, NSE Indices & Global Futures**")

# Fetch live USD to INR conversion rate
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_usd_to_inr():
    """Fetch live USD to INR exchange rate from yfinance"""
    try:
        inr_data = yf.download("INR=X", period="1d", progress=False)
        if not inr_data.empty:
            rate = inr_data['Close'].iloc[-1]
            st.sidebar.success(f"💱 Live USD/INR: ₹{rate:.2f}")
            return rate
    except Exception as e:
        pass
    
    # Fallback to default value
    st.sidebar.warning("⚠️ Using default USD/INR = ₹83.50")
    return 83.50

USD_TO_INR = get_usd_to_inr()

ASSETS = {
    "🇮🇳 MCX Commodities": {
        "MCXGOLD": ("Gold (MCX India)", "₹", "GC=F"),
        "MCXSILVER": ("Silver (MCX India)", "₹", "SI=F"),
        "MCXNATURALGAS": ("Natural Gas (MCX India)", "₹", "NG=F"),
        "MCXCRUDE": ("Crude Oil (MCX India)", "₹", "CL=F"),
        "MCXCOPPER": ("Copper (MCX India)", "₹", "HG=F"),
        "MCXZINC": ("Zinc (MCX India)", "₹", "ZW=F"),
        "MCXLEAD": ("Lead (MCX India)", "₹", "LD=F"),
    },
    "📊 NSE Index Options": {
        "NIFTY": ("NIFTY 50 Index", "₹", "^NSEI"),
        "SENSEX": ("SENSEX Index", "₹", "^BSESN"),
        "BANKNIFTY": ("BANK NIFTY Index", "₹", "^NSEBANK"),
    },
    "🌍 Global Futures": {
        "GC=F": ("Gold Futures (Global)", "$", "GC=F"),
        "CL=F": ("Crude Oil Futures (Global)", "$", "CL=F"),
        "SI=F": ("Silver Futures (Global)", "$", "SI=F"),
        "NG=F": ("Natural Gas Futures (Global)", "$", "NG=F"),
    }
}

# USD to INR conversion rate (approximate, should be updated daily)
USD_TO_INR = 83.5

# Sidebar configuration
with st.sidebar:
    st.header("⚙️ Configuration")

    st.markdown("---")
    
    # Asset category selector
    category = st.selectbox("📂 Select Asset Category", list(ASSETS.keys()))
    asset_name = st.selectbox("🎯 Select Asset", list(ASSETS[category].keys()), 
                              format_func=lambda x: ASSETS[category][x][0])
    
    display_name, currency, yf_ticker = ASSETS[category][asset_name]
    
    st.markdown("---")
    period = st.selectbox("📅 Data Period", ["1mo", "3mo", "6mo", "1y"], index=2)
    
    st.markdown("---")
    st.info("📊 **Mode**: INTRADAY OPTIONS ONLY\nFocused on today's trading signals based on live candlestick patterns.")
    st.markdown(f"**Display Name:** {display_name}")
    st.markdown(f"**Currency:** {currency}")
    st.markdown(f"**Yahoo Ticker:** {yf_ticker}")

    target_forecast_refresh = st.toggle(
        "🎯 Refresh target forecasts every 1s",
        value=True,
        help="Refreshes the separate target-price forecast tab every second for all commodities."
    )
    
    if asset_name.startswith("MCX"):
        mcx_live_refresh = st.toggle(
            "🔄 Refresh MCX live data every 1s",
            value=True,
            help="Polls the official MCX market-watch source every second while an MCX commodity is selected."
        )
        st.info("📌 **MCX DATA**: Using official MCX market-watch prices first; yfinance conversion is fallback/history.")
    elif asset_name in ["NIFTY", "SENSEX", "BANKNIFTY"]:
        nse_live_refresh = st.toggle(
            "🔄 Refresh NSE live data every 1s",
            value=True,
            help="Polls NSE live data every second for real-time Indian index prices."
        )
        st.info("📌 **NSE DATA**: Using NSE live API with yfinance fallback for real-time index data.")
    elif asset_name in ["GC=F", "CL=F", "SI=F", "NG=F", "HG=F", "ZW=F", "ZS=F"]:
        global_live_refresh = st.toggle(
            "🔄 Refresh Global live data every 1s",
            value=True,
            help="Polls global futures data every second for real-time international prices."
        )
        st.info("📌 **GLOBAL DATA**: Using Investing.com commodities first with yfinance fallback.")
    else:
        nse_live_refresh = False
        global_live_refresh = False
    
    # Option pricing parameters
    st.markdown("---")
    st.subheader("⚡ Options Parameters")
    strike_interval = st.number_input("Strike Interval", value=100, step=50, min_value=1)
    
    # Fixed for intraday trading
    days_to_expiry = 1  # Intraday expiry (same day)

# ============ DATA FETCHING & PROCESSING ============

@st.cache_data(ttl=3600)
def get_mcx_conversion_factors():
    """
    Fetch live MCX reference prices and calculate conversion factors dynamically.
    Conversion factor = MCX price / Global futures price (converted to INR)
    
    Returns:
        Dict with conversion factors for each MCX commodity
    """
    try:
        # MCX reference prices (in ₹) - fetched from MCX website
        # These are typical/baseline prices used to calibrate conversion
        mcx_reference = {
            "MCXNATURALGAS": 260.50,  # Natural Gas (26 May contract)
            "MCXGOLD": 152589.00,      # Gold (05 Jun contract)
            "MCXSILVER": 261999.00,    # Silver (03 Jul contract)
            "MCXCRUDE": 9022.00,       # Crude Oil (18 May contract)
            "MCXCOPPER": 1325.40,      # Copper (29 May contract)
            "MCXZINC": 348.40,         # Zinc (29 May contract)
            "MCXLEAD": 200.30,         # Lead (29 May contract)
        }
        
        # Fetch global futures reference prices
        global_futures = {
            "MCXNATURALGAS": "NG=F",
            "MCXGOLD": "GC=F",
            "MCXSILVER": "SI=F",
            "MCXCRUDE": "CL=F",
            "MCXCOPPER": "HG=F",
        }
        
        conversion_factors = {}
        
        for mcx_ticker, futures_ticker in global_futures.items():
            try:
                # Fetch global futures price
                data = yf.download(futures_ticker, period="1d", progress=False)
                if not data.empty:
                    global_price_usd = data['Close'].iloc[-1]
                    global_price_inr = global_price_usd * USD_TO_INR
                    
                    mcx_ref = mcx_reference.get(mcx_ticker, 1)
                    
                    # Calculate conversion factor
                    if global_price_inr > 0:
                        factor = mcx_ref / global_price_inr
                        conversion_factors[mcx_ticker] = factor
                    else:
                        conversion_factors[mcx_ticker] = 1.0
            except Exception as e:
                st.warning(f"Could not fetch conversion factor for {mcx_ticker}: {e}")
                conversion_factors[mcx_ticker] = 1.0
        
        # For commodities without direct futures mapping
        conversion_factors["MCXZINC"] = 1.0
        conversion_factors["MCXLEAD"] = 1.0
        
        return conversion_factors
        
    except Exception as e:
        st.warning(f"Error calculating MCX conversion factors: {e}")
        # Return default factors if calculation fails
        return {
            "MCXNATURALGAS": 1.13,
            "MCXGOLD": 31.1035,
            "MCXSILVER": 31.1035,
            "MCXCRUDE": 1.0,
            "MCXCOPPER": 1.0,
            "MCXZINC": 1.0,
            "MCXLEAD": 1.0,
        }

# Get conversion factors at app start
MCX_FACTORS = get_mcx_conversion_factors()

def convert_price_for_display(price: float, asset_name: str, raw_currency: str) -> Tuple[float, str]:
    """
    Convert price to appropriate display currency for MCX commodities using live conversion factors.
    
    Args:
        price: Raw price from yfinance (global futures in USD)
        asset_name: Asset identifier
        raw_currency: Original currency ($)
    
    Returns:
        Tuple of (converted_price, display_currency)
    """
    if asset_name.startswith("MCX"):
        # Convert USD to INR
        converted = price * USD_TO_INR
        
        # Apply dynamic MCX conversion factor based on live prices
        factor = MCX_FACTORS.get(asset_name, 1.0)
        converted = converted * factor
        
        return converted, "₹"
    else:
        return price, raw_currency


@st.cache_data(ttl=300)
def fetch_data(ticker, period):
    """
    Fetch historical data from yfinance.
    
    Args:
        ticker: Symbol ticker
        period: Time period
    
    Returns:
        DataFrame with OHLCV data
    """
    try:
        data = yf.download(ticker, period=period, progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        data.columns = data.columns.str.strip().str.title()
        return data
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return None


def convert_mcx_history_to_inr(data: pd.DataFrame, asset_name: str) -> pd.DataFrame:
    """Convert yfinance global futures history into the app's MCX INR display scale."""
    if not asset_name.startswith("MCX"):
        return data

    converted = data.copy()
    factor = MCX_FACTORS.get(asset_name, 1.0)
    multiplier = USD_TO_INR * factor

    for col in ["Open", "High", "Low", "Close", "Adj Close"]:
        if col in converted.columns:
            converted[col] = converted[col] * multiplier

    return converted


@st.cache_data(ttl=1, show_spinner=False)
def fetch_live_mcx_quote(asset_name: str):
    """Fetch a fresh MCX quote from the official market-watch source."""
    try:
        return get_live_mcx_quote(asset_name)
    except Exception as e:
        return {"error": str(e), "source": "MCX market watch"}


def apply_live_mcx_quote(data: pd.DataFrame, quote: dict) -> pd.DataFrame:
    """Patch the latest candle with the latest MCX market-watch quote."""
    if not quote or quote.get("price") is None:
        return data

    updated = data.copy()
    last_idx = updated.index[-1]
    price = float(quote["price"])

    updated.at[last_idx, "Close"] = price
    if "Open" in updated.columns and quote.get("open") is not None:
        updated.at[last_idx, "Open"] = float(quote["open"])
    if "High" in updated.columns:
        quote_high = float(quote["high"]) if quote.get("high") is not None else price
        updated.at[last_idx, "High"] = max(quote_high, price)
    if "Low" in updated.columns:
        quote_low = float(quote["low"]) if quote.get("low") is not None else price
        updated.at[last_idx, "Low"] = min(quote_low, price)
    if "Volume" in updated.columns and quote.get("volume") is not None:
        updated.at[last_idx, "Volume"] = float(quote["volume"])

    return updated


@st.cache_data(ttl=1, show_spinner=False)
def fetch_live_nse_quote(asset_name: str):
    """Fetch a fresh NSE index quote."""
    try:
        return get_live_nse_quote(asset_name)
    except Exception as e:
        return {"error": str(e), "source": "NSE API"}

@st.cache_data(ttl=1, show_spinner=False)
def fetch_live_global_quote(asset_name: str):
    """Fetch a fresh global futures quote."""
    try:
        return get_live_global_quote(asset_name)
    except Exception as e:
        return {"error": str(e), "source": "Global API"}


def apply_live_nse_quote(data: pd.DataFrame, quote: dict) -> pd.DataFrame:
    """Patch the latest candle with the latest NSE live quote."""
    if not quote or quote.get("price") is None:
        return data

    updated = data.copy()
    last_idx = updated.index[-1]
    price = float(quote["price"])

    updated.at[last_idx, "Close"] = price
    if "Open" in updated.columns and quote.get("open") is not None:
        updated.at[last_idx, "Open"] = float(quote["open"])
    if "High" in updated.columns:
        quote_high = float(quote["high"]) if quote.get("high") is not None else price
        updated.at[last_idx, "High"] = max(quote_high, price)
    if "Low" in updated.columns:
        quote_low = float(quote["low"]) if quote.get("low") is not None else price
        updated.at[last_idx, "Low"] = min(quote_low, price)
    if "Volume" in updated.columns and quote.get("volume") is not None:
        updated.at[last_idx, "Volume"] = float(quote["volume"])

    return updated

def apply_live_global_quote(data: pd.DataFrame, quote: dict) -> pd.DataFrame:
    """Patch the latest candle with the latest global futures quote."""
    if not quote or quote.get("price") is None:
        return data

    updated = data.copy()
    last_idx = updated.index[-1]
    price = float(quote["price"])

    updated.at[last_idx, "Close"] = price
    if "Open" in updated.columns and quote.get("open") is not None:
        updated.at[last_idx, "Open"] = float(quote["open"])
    if "High" in updated.columns:
        quote_high = float(quote["high"]) if quote.get("high") is not None else price
        updated.at[last_idx, "High"] = max(quote_high, price)
    if "Low" in updated.columns:
        quote_low = float(quote["low"]) if quote.get("low") is not None else price
        updated.at[last_idx, "Low"] = min(quote_low, price)
    if "Volume" in updated.columns and quote.get("volume") is not None:
        updated.at[last_idx, "Volume"] = float(quote["volume"])

    return updated


COMMODITY_FORECAST_ASSETS = {
    **ASSETS["🇮🇳 MCX Commodities"],
    **ASSETS["🌍 Global Futures"],
}


@st.cache_data(ttl=1, show_spinner=False)
def fetch_forecast_history(yf_ticker: str, asset_key: str) -> pd.DataFrame:
    """Fetch short intraday candles for the fixed target-price forecast tab."""
    try:
        history = yf.download(yf_ticker, period="5d", interval="5m", progress=False)
        if history.empty:
            history = yf.download(yf_ticker, period="1mo", progress=False)

        if isinstance(history.columns, pd.MultiIndex):
            history.columns = history.columns.get_level_values(0)
        history.columns = history.columns.str.strip().str.title()

        if asset_key.startswith("MCX"):
            history = convert_mcx_history_to_inr(history, asset_key)

        return history.tail(240)
    except Exception:
        return pd.DataFrame()


def add_forecast_indicators(history: pd.DataFrame, close_col_name: str = "Close") -> pd.DataFrame:
    """Add the indicators used by the target-price forecast engine."""
    if history.empty or close_col_name not in history.columns:
        return history

    enriched = history.copy()
    try:
        enriched["SMA_10"] = ta.trend.sma_indicator(enriched[close_col_name], window=10)
        enriched["SMA_20"] = ta.trend.sma_indicator(enriched[close_col_name], window=20)
        enriched["RSI_14"] = ta.momentum.rsi(enriched[close_col_name], window=14)
        macd_calc = ta.trend.MACD(enriched[close_col_name])
        enriched["MACD"] = macd_calc.macd()
        enriched["MACD_Signal"] = macd_calc.macd_signal()
        enriched["ATR"] = ta.volatility.average_true_range(
            enriched["High"],
            enriched["Low"],
            enriched[close_col_name],
        )
        if "Volume" in enriched.columns:
            enriched["Volume_SMA"] = enriched["Volume"].rolling(window=20).mean()
            enriched["Volume_Trend"] = (
                (enriched["Volume"] - enriched["Volume_SMA"]) / enriched["Volume_SMA"] * 100
            )
    except Exception:
        pass

    return enriched


@st.cache_data(ttl=1, show_spinner=False)
def get_forecast_sentiment(asset_label: str) -> dict:
    """Refresh commodity-news sentiment with the same 1-second cadence as quotes."""
    query = (
        asset_label.replace("(MCX India)", "")
        .replace("(Global)", "")
        .replace("Futures", "")
        .strip()
    )
    return analyze_news_sentiment(query.upper(), num_articles=5)


def get_forecast_live_quote(asset_key: str, yf_ticker: str) -> dict:
    """Fetch the live quote source appropriate for the commodity forecast table."""
    if asset_key.startswith("MCX"):
        return fetch_live_mcx_quote(asset_key) or {}
    return fetch_live_global_quote(yf_ticker) or {}


def format_forecast_price(value: float, currency_symbol: str) -> str:
    """Format forecast prices consistently inside dataframe rows."""
    try:
        return f"{currency_symbol}{float(value):,.2f}"
    except Exception:
        return f"{currency_symbol}0.00"


# Fetch data
data = fetch_data(yf_ticker, period)

if data is None or data.empty:
    st.error("No data available for the selected ticker.")
    st.stop()

# Standardize column names
close_col = "Close" if "Close" in data.columns else "Adj Close"
volume_col = "Volume" if "Volume" in data.columns else None

data = data.dropna(subset=[close_col])
if volume_col and volume_col in data.columns:
    data = data.dropna(subset=[volume_col])

mcx_quote = {}
nse_quote = {}
global_quote = {}

if asset_name.startswith("MCX"):
    data = convert_mcx_history_to_inr(data, asset_name)
    mcx_quote = fetch_live_mcx_quote(asset_name) or {}
    data = apply_live_mcx_quote(data, mcx_quote)
elif asset_name in ["NIFTY", "SENSEX", "BANKNIFTY"]:
    nse_quote = fetch_live_nse_quote(asset_name) or {}
    data = apply_live_nse_quote(data, nse_quote)
elif asset_name in ["GC=F", "CL=F", "SI=F", "NG=F", "HG=F", "ZW=F", "ZS=F"]:
    global_quote = fetch_live_global_quote(asset_name) or {}
    data = apply_live_global_quote(data, global_quote)

# ============ TECHNICAL INDICATORS ============

# Add technical indicators
data["SMA_10"] = ta.trend.sma_indicator(data[close_col], window=10)
data["SMA_20"] = ta.trend.sma_indicator(data[close_col], window=20)
data["EMA_12"] = ta.trend.ema_indicator(data[close_col], window=12)
data["RSI_14"] = ta.momentum.rsi(data[close_col], window=14)
macd = ta.trend.MACD(data[close_col])
data["MACD"] = macd.macd()
data["MACD_Signal"] = macd.macd_signal()
data["MACD_Diff"] = macd.macd_diff()
bb = ta.volatility.BollingerBands(data[close_col], window=20, window_dev=2)
data["BB_High"] = bb.bollinger_hband()
data["BB_Low"] = bb.bollinger_lband()
data["BB_Mid"] = bb.bollinger_mavg()
data["ATR"] = ta.volatility.average_true_range(data["High"], data["Low"], data[close_col])

# Calculate volume trend
if volume_col and volume_col in data.columns:
    data["Volume_SMA"] = data[volume_col].rolling(window=20).mean()
    data["Volume_Trend"] = (data[volume_col] - data["Volume_SMA"]) / data["Volume_SMA"] * 100
else:
    data["Volume_Trend"] = 0

data["Daily Change"] = data[close_col].pct_change() * 100

# Current metrics
current_price_raw = data[close_col].iloc[-1]
if asset_name.startswith("MCX"):
    current_price, display_currency = float(current_price_raw), "₹"
else:
    current_price, display_currency = convert_price_for_display(current_price_raw, asset_name, currency)

last_change = data["Daily Change"].iloc[-1]
sma_10 = data["SMA_10"].iloc[-1]
sma_20 = data["SMA_20"].iloc[-1]
rsi = data["RSI_14"].iloc[-1]
macd_val = data["MACD"].iloc[-1]
macd_signal = data["MACD_Signal"].iloc[-1]
volume_trend = data["Volume_Trend"].iloc[-1] if "Volume_Trend" in data.columns else 0

# ============ MAIN DISPLAY ============

# Current metrics
st.subheader(f"📊 {display_name} | Current Price: {display_currency}{current_price:.2f}")
if asset_name.startswith("MCX"):
    if mcx_quote.get("price") is not None:
        quote_time = mcx_quote.get("timestamp") or datetime.now()
        expiry_text = f" | Expiry: {mcx_quote['expiry']}" if mcx_quote.get("expiry") else ""
        st.success(
            f"📡 Official MCX market-watch quote: {display_currency}{mcx_quote['price']:.2f}"
            f" | refreshed {quote_time.strftime('%H:%M:%S')}{expiry_text}"
        )
    elif mcx_quote.get("error"):
        st.warning(f"📡 MCX market-watch unavailable: {mcx_quote['error']}. Showing converted yfinance fallback.")
    else:
        st.warning("📡 MCX market-watch did not return a quote. Showing converted yfinance fallback.")
elif asset_name in ["NIFTY", "SENSEX", "BANKNIFTY"]:
    if nse_quote.get("price") is not None:
        quote_time = nse_quote.get("timestamp") or datetime.now()
        change_text = f" | Change: {nse_quote['change']:.2f} ({nse_quote['change_percent']:.2f}%)"
        st.success(
            f"📡 NSE Live quote: {display_currency}{nse_quote['price']:.2f}{change_text}"
            f" | refreshed {quote_time.strftime('%H:%M:%S')} | Source: {nse_quote.get('source', 'NSE')}"
        )
    elif nse_quote.get("error"):
        st.warning(f"📡 NSE live data unavailable: {nse_quote['error']}. Showing yfinance fallback.")
    else:
        st.warning("📡 NSE live data not available. Showing yfinance fallback.")
elif asset_name in ["GC=F", "CL=F", "SI=F", "NG=F", "HG=F", "ZW=F", "ZS=F"]:
    if global_quote.get("price") is not None:
        quote_time = global_quote.get("timestamp") or datetime.now()
        change_text = f" | Change: {global_quote['change']:.2f} ({global_quote['change_percent']:.2f}%)"
        st.success(
            f"📡 Global Live quote: {display_currency}{global_quote['price']:.2f}{change_text}"
            f" | refreshed {quote_time.strftime('%H:%M:%S')} | Source: {global_quote.get('source', 'Global')}"
        )
    elif global_quote.get("error"):
        st.warning(f"📡 Global live data unavailable: {global_quote['error']}. Showing yfinance fallback.")
    else:
        st.warning("📡 Global live data not available. Showing yfinance fallback.")
col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("Price Change", f"{last_change:.2f}%", delta=last_change)
col2.metric("RSI (14)", f"{rsi:.1f}", "Overbought ↑" if rsi > 70 else "Oversold ↓" if rsi < 30 else "Neutral →")
col3.metric("SMA 10/20", f"{sma_10:.0f}/{sma_20:.0f}", "↑ Bullish" if sma_10 > sma_20 else "↓ Bearish")
col4.metric("MACD", f"{macd_val:.6f}", "↑" if macd_val > macd_signal else "↓")
col5.metric("ATR", f"{data['ATR'].iloc[-1]:.2f}", "Volatility")
col6.metric("Volume Trend", f"{volume_trend:.1f}%", "High ↑" if volume_trend > 20 else "Low ↓")

# ============ TABS ============

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🎯 OPTIONS SIGNAL", 
    "📈 Price & Volume", 
    "📊 Technical Indicators",
    "📰 News Sentiment",
    "💰 INTRADAY OPTIONS",
    "🔧 Analysis Details",
    "🎯 Target Price Forecast"
])

# ============ TAB 1: OPTIONS SIGNAL (MAIN FEATURE) ============

with tab1:
    st.markdown("## 🎯 INTRADAY OPTIONS SIGNAL - TODAY'S TRADE")
    st.info("⏰ Real-time signals based on current candlestick patterns and technical setup")
    
    # Get candlestick patterns (intraday focus)
    pattern_result = detect_candlestick_patterns(data, close_col)
    
    # Get support/resistance (intraday levels)
    sr_levels = calculate_support_resistance(data, close_col)
    
    # Get intraday options recommendation
    intraday_rec = recommend_intraday_options(data, current_price, strike_interval, close_col)
    
    # Get volume anomaly
    volume_anomaly = detect_volume_anomaly(data[volume_col] if volume_col else data["Close"], window=20)
    
    # Get sentiment
    sentiment_data = analyze_news_sentiment(asset_name.replace("MCX", "").upper(), num_articles=5)
    
    # Calculate technical signal
    technical_signal = "BULLISH" if (sma_10 > sma_20 and rsi < 70) else "BEARISH" if (sma_10 < sma_20 and rsi > 30) else "NEUTRAL"
    
    # Multi-factor score
    multi_score = calculate_multi_factor_score(
        price_trend_signal="BULLISH" if pattern_result["signal"] == "BUY_CALL" else "BEARISH" if pattern_result["signal"] == "BUY_PUT" else "NEUTRAL",
        technical_signal=technical_signal,
        volume_score=volume_anomaly.get("anomaly_score", 0),
        sentiment_score=sentiment_data.get("overall_sentiment", 0),
        greeks_signal=technical_signal
    )
    
    # Display main signal
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        st.markdown("### SIGNAL")
        if pattern_result["signal"] == "BUY_CALL":
            st.success(f"🟢 BUY CALL\n\n{multi_score['bullish_score']:.0f}% Bullish")
        elif pattern_result["signal"] == "BUY_PUT":
            st.warning(f"🔴 BUY PUT\n\n{multi_score['bearish_score']:.0f}% Bearish")
        else:
            st.info(f"🟡 WAIT\n\nNo Clear Setup")
    
    with col2:
        st.markdown("### INTRADAY LEVELS")
        
        col_levels_l, col_levels_r = st.columns(2)
        
        with col_levels_l:
            st.markdown(f"**Current Price**\n# {display_currency}{current_price:.2f}")
            st.markdown(f"**Support Level**\n# {display_currency}{sr_levels['support']:.2f}")
        
        with col_levels_r:
            st.markdown(f"**Resistance Level**\n# {display_currency}{sr_levels['resistance']:.2f}")
            st.markdown(f"**Pivot Point**\n# {display_currency}{sr_levels['pivot']:.2f}")
        
        st.divider()
        
        # Show distance to support/resistance
        dist_to_support = ((current_price - sr_levels['support']) / sr_levels['support']) * 100
        dist_to_resistance = ((sr_levels['resistance'] - current_price) / current_price) * 100
        
        col_dist_l, col_dist_r = st.columns(2)
        
        with col_dist_l:
            st.caption(f"📉 To Support: {dist_to_support:.1f}%")
        
        with col_dist_r:
            st.caption(f"📈 To Resistance: {dist_to_resistance:.1f}%")
    
    with col3:
        st.markdown("### PATTERN")
        
        pattern_name = pattern_result.get("current_pattern", "No Pattern")
        pattern_conf = pattern_result.get("confidence", 0)
        
        color = "green" if pattern_conf > 70 else "orange" if pattern_conf > 50 else "red"
        
        st.markdown(f"<h4 style='text-align: center;'>{pattern_name}</h4>", unsafe_allow_html=True)
        st.markdown(f"<h1 style='text-align: center; color: {color};'>{pattern_conf:.0f}%</h1>", unsafe_allow_html=True)
        
        st.markdown("**Confidence**")
        if pattern_conf > 70:
            st.markdown("✅ Strong setup\n✅ High probability")
        elif pattern_conf > 50:
            st.markdown("⚠️ Moderate setup\n⚠️ Proceed with caution")
        else:
            st.markdown("❌ Weak signal\n❌ Wait for clarity")
    
    st.divider()
    
    # Multi-factor breakdown
    st.markdown("### 📊 Multi-Factor Analysis")
    
    col_factors = st.columns(5)
    factors = multi_score["factors"]
    
    factor_names = ["Price Trend", "Technical", "Volume", "Sentiment", "Greeks"]
    factor_keys = ["price_trend", "technical", "volume", "sentiment", "greeks"]
    
    for i, (col, name, key) in enumerate(zip(col_factors, factor_names, factor_keys)):
        score = factors[key]
        with col:
            color = "green" if score > 60 else "orange" if score > 40 else "red"
            st.markdown(f"""
            <div style='text-align: center; padding: 10px; border-radius: 5px; background-color: {color}20;'>
            <h4>{name}</h4>
            <h2 style='color: {color};'>{score:.0f}%</h2>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Actionable recommendation
    st.markdown("### 💡 TODAY'S TRADE SETUP")
    
    if pattern_result["signal"] == "BUY_CALL":
        st.success(f"""
        **🟢 BUY CALL OPTION - BULLISH SETUP**
        
        **Current Technical Setup:**
        - Price is at **{display_currency}{current_price:.2f}**
        - Support: **{display_currency}{sr_levels['support']:.2f}** | Resistance: **{display_currency}{sr_levels['resistance']:.2f}**
        - Pattern: **{pattern_name}** ({pattern_conf:.0f}% confidence)
        
        **RECOMMENDATION:**
        - **Strike Price**: {display_currency}{estimate_atm_strike(current_price, strike_interval):.0f} (ATM) or {display_currency}{estimate_atm_strike(current_price, strike_interval) + strike_interval:.0f} (OTM)
        - **Expected Target**: {display_currency}{sr_levels['resistance']:.2f}
        - **Stop Loss**: {display_currency}{sr_levels['support']:.2f}
        - **Trading Style**: Intraday only (same-day exit recommended)
        """)
    elif pattern_result["signal"] == "BUY_PUT":
        st.warning(f"""
        **🔴 BUY PUT OPTION - BEARISH SETUP**
        
        **Current Technical Setup:**
        - Price is at **{display_currency}{current_price:.2f}**
        - Support: **{display_currency}{sr_levels['support']:.2f}** | Resistance: **{display_currency}{sr_levels['resistance']:.2f}**
        - Pattern: **{pattern_name}** ({pattern_conf:.0f}% confidence)
        
        **RECOMMENDATION:**
        - **Strike Price**: {display_currency}{estimate_atm_strike(current_price, strike_interval):.0f} (ATM) or {display_currency}{estimate_atm_strike(current_price, strike_interval) - strike_interval:.0f} (OTM)
        - **Expected Target**: {display_currency}{sr_levels['support']:.2f}
        - **Stop Loss**: {display_currency}{sr_levels['resistance']:.2f}
        - **Trading Style**: Intraday only (same-day exit recommended)
        """)
    else:
        st.info(f"""
        **🟡 WAIT FOR CLEARER SETUP**
        - Current Pattern: **{pattern_name}**
        - No strong directional bias detected
        - Recommended: Monitor support ({display_currency}{sr_levels['support']:.2f}) and resistance ({display_currency}{sr_levels['resistance']:.2f}) levels
        - Action: Wait for breakout or pattern confirmation
        """)

# ============ TAB 2: PRICE & VOLUME ============

with tab2:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Price Action with Moving Averages")
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=data.index, y=data[close_col], name="Close", mode="lines"))
        fig1.add_trace(go.Scatter(x=data.index, y=data["SMA_10"], name="SMA 10", mode="lines"))
        fig1.add_trace(go.Scatter(x=data.index, y=data["SMA_20"], name="SMA 20", mode="lines"))
        fig1.add_trace(go.Scatter(x=data.index, y=data["BB_High"], name="BB Upper", mode="lines", line=dict(dash="dash")))
        fig1.add_trace(go.Scatter(x=data.index, y=data["BB_Low"], name="BB Lower", mode="lines", line=dict(dash="dash"), fill="tonexty"))
        fig1.update_layout(height=400, xaxis_title="Date", yaxis_title="Price", hovermode="x unified")
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        st.subheader("Volume Analysis")
        if volume_col and volume_col in data.columns:
            fig2 = go.Figure()
            colors = ['red' if data[close_col].iloc[i] < data[close_col].iloc[i-1] else 'green' for i in range(1, len(data))]
            fig2.add_trace(go.Bar(x=data.index[1:], y=data[volume_col].iloc[1:], marker_color=colors, name="Volume"))
            fig2.add_trace(go.Scatter(x=data.index, y=data["Volume_SMA"], name="Volume SMA", mode="lines"))
            fig2.update_layout(height=400, xaxis_title="Date", yaxis_title="Volume")
            st.plotly_chart(fig2, use_container_width=True)

# ============ TAB 3: TECHNICAL INDICATORS ============

with tab3:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("RSI (Relative Strength Index)")
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=data.index, y=data["RSI_14"], name="RSI 14", fill="tozeroy"))
        fig3.add_hline(y=70, line_dash="dash", line_color="red")
        fig3.add_hline(y=30, line_dash="dash", line_color="green")
        fig3.update_layout(height=350, yaxis_range=[0, 100], xaxis_title="Date", yaxis_title="RSI")
        st.plotly_chart(fig3, use_container_width=True)
    
    with col2:
        st.subheader("MACD")
        fig4 = go.Figure()
        fig4.add_trace(go.Scatter(x=data.index, y=data["MACD"], name="MACD", mode="lines"))
        fig4.add_trace(go.Scatter(x=data.index, y=data["MACD_Signal"], name="Signal", mode="lines"))
        fig4.add_trace(go.Bar(x=data.index, y=data["MACD_Diff"], name="Histogram"))
        fig4.update_layout(height=350, xaxis_title="Date", yaxis_title="MACD")
        st.plotly_chart(fig4, use_container_width=True)

# ============ TAB 4: NEWS SENTIMENT ============

with tab4:
    st.subheader(f"📰 Market Sentiment for {asset_name}")
    
    sentiment_data = analyze_news_sentiment(asset_name.replace("MCX", "").upper())
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        sentiment_scale = sentiment_data["sentiment_scale_100"]
        color = "green" if sentiment_scale > 60 else "orange" if sentiment_scale > 40 else "red"
        
        st.markdown(f"""
        <div style='text-align: center; padding: 20px; border-radius: 10px; background-color: {color}20;'>
        <h3>Overall Sentiment</h3>
        <h1 style='color: {color};'>{sentiment_scale:.0f}/100</h1>
        <h4>{sentiment_data['sentiment_label']}</h4>
        <p>Confidence: {sentiment_data['confidence']:.0f}%</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("### Top News Stories")
        if sentiment_data.get("top_articles"):
            for article in sentiment_data.get("top_articles", [])[:5]:
                sentiment_emoji = "📈" if article["sentiment"] > 0.2 else "📉" if article["sentiment"] < -0.2 else "➡️"
                st.markdown(f"{sentiment_emoji} **{article['headline'][:80]}...**")
                st.caption(f"Source: {article['source']} | Sentiment: {article['sentiment']:.2f}")
        else:
            st.info("No articles available for sentiment analysis")

# ============ TAB 5: INTRADAY OPTIONS WITH CANDLESTICK PATTERNS ============

with tab5:
    st.markdown("## 💰 INTRADAY OPTIONS - TODAY'S TRADES")
    st.markdown("Based on candlestick patterns and support/resistance levels")
    
    # Get candlestick pattern analysis
    pattern_result = detect_candlestick_patterns(data, close_col)
    
    # Get support/resistance
    sr_levels = calculate_support_resistance(data, close_col)
    
    # Get intraday options recommendation
    intraday_rec = recommend_intraday_options(data, current_price, strike_interval, close_col)
    
    # Display pattern analysis
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        pattern_emoji = "🔴" if pattern_result["signal"] == "BUY_PUT" else "🟢" if pattern_result["signal"] == "BUY_CALL" else "🟡"
        st.metric("Pattern", pattern_result["current_pattern"], delta=f"{pattern_result['confidence']:.0f}% {pattern_emoji}")
    
    with col2:
        signal_delta = "→" if pattern_result["signal"] != "HOLD" else "—"
        st.metric("Signal", pattern_result["signal"].replace("_", " "), delta=signal_delta)
    
    with col3:
        st.metric("Support", f"{display_currency}{sr_levels['support']:.2f}", delta=f"↓ {abs(sr_levels['support'] - current_price):.2f}")
    
    with col4:
        st.metric("Resistance", f"{display_currency}{sr_levels['resistance']:.2f}", delta=f"↑ {sr_levels['resistance'] - current_price:.2f}")
    
    st.divider()
    
    # Display today's recommended trades
    if intraday_rec.get("today_trades"):
        st.subheader("📋 TODAY'S RECOMMENDED OPTIONS")
        
        for idx, trade in enumerate(intraday_rec["today_trades"], 1):
            col1, col2, col3 = st.columns([1, 2, 1])
            
            with col1:
                trade_type = trade["type"]
                priority = trade["priority"]
                
                if trade_type == "CALL":
                    st.success(f"🟢 {trade_type}\n**{priority}**")
                else:
                    st.error(f"🔴 {trade_type}\n**{priority}**")
            
            with col2:
                st.markdown(f"""
                **Strike Price:** ₹{trade['strike']:.0f}
                
                **Entry Price:** ₹{trade['entry_price']:.2f}
                
                **Target:** ₹{trade['target_price']:.2f} | **Stop Loss:** ₹{trade['stop_loss']:.2f}
                
                **Pattern:** {trade['pattern']}
                """)
            
            with col3:
                if "upside_potential" in trade:
                    potential = trade["upside_potential"]
                    st.metric("Potential", f"{potential:+.1f}%", delta=f"{potential:+.1f}%")
                else:
                    potential = trade["downside_potential"]
                    st.metric("Potential", f"{potential:+.1f}%", delta=f"{potential:+.1f}%")
                
                st.metric("Confidence", f"{trade['confidence']:.0f}%")
            
            st.divider()
    else:
        st.info(f"⚠️ {intraday_rec.get('message', 'No clear trading pattern detected for today.')}")
    
    # Display candlestick patterns found
    st.subheader("📊 Candlestick Patterns Detected")
    
    if pattern_result["patterns"]:
        for pattern, direction, confidence in pattern_result["patterns"]:
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.write(f"**{pattern}**")
            with col2:
                direction_emoji = "📈" if direction == "BULLISH" else "📉" if direction == "BEARISH" else "➡️"
                st.write(f"{direction_emoji} {direction}")
            with col3:
                st.write(f"**{confidence}%** Confidence")
    else:
        st.write("No recognized candlestick patterns detected in recent data.")
    
    # Intraday price targets
    st.subheader("🎯 Intraday Price Targets")
    targets = get_intraday_price_targets(current_price, intraday_rec["signal"])
    
    target_col1, target_col2, target_col3, target_col4, target_col5 = st.columns(5)
    
    with target_col1:
        st.metric("Very Bearish", f"{display_currency}{targets['very_bearish']:.2f}")
    with target_col2:
        st.metric("Bearish", f"{display_currency}{targets['bearish']:.2f}")
    with target_col3:
        st.metric("Current", f"{display_currency}{targets['current']:.2f}", delta="0")
    with target_col4:
        st.metric("Bullish", f"{display_currency}{targets['bullish']:.2f}")
    with target_col5:
        st.metric("Very Bullish", f"{display_currency}{targets['very_bullish']:.2f}")

# ============ TAB 6: ANALYSIS DETAILS ============

with tab6:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Volume Anomaly")
        vol_anom = volume_anomaly
        st.write(f"**Current Volume:** {vol_anom['current_volume']:,.0f}")
        st.write(f"**Average Volume:** {vol_anom['avg_volume']:,.0f}")
        st.write(f"**Anomaly Score:** {vol_anom['anomaly_score']:.0f}%")
        st.write(f"**Type:** {vol_anom['anomaly_type']}")
        st.write(f"**Trend:** {vol_anom['volume_trend']}")
    
    with col2:
        st.subheader("🎯 Options Metrics (Greeks)")
        T = days_to_expiry / 365
        atm_strike = estimate_atm_strike(current_price, strike_interval)
        greeks_call = calculate_greeks(current_price, atm_strike, T, sigma=0.2)
        
        if greeks_call.get("premium") and greeks_call.get("premium") > 0:
            st.write(f"**ATM Strike:** {display_currency}{atm_strike:.0f}")
            st.write(f"**Call Premium (ATM):** {display_currency}{greeks_call['premium']:.2f}")
            st.write(f"**Delta:** {greeks_call['delta']:.3f}")
            st.write(f"**Gamma:** {greeks_call['gamma']:.6f}")
            st.write(f"**Theta (per day):** {greeks_call['theta']:.4f}")
            st.write(f"**Vega:** {greeks_call['vega']:.3f}")
    
    st.divider()
    
    st.subheader("🔗 LIVE DATA INTEGRATION - MCX MARKET WATCH")

    st.markdown("""
    ### 🚀 Current MCX Source

    MCX commodities now use the official MCX market-watch data source first.
    The latest quote patches the current candle, while historical candles still use
    yfinance converted to the MCX INR scale as a fallback/history source.

    ### 📊 Data Sources Comparison:
    """)
    
    data_sources = {
        "Data Type": ["MCX Commodities", "MCX History", "NSE/BSE Indices", "Global Futures", "Refresh", "Options Premiums"],
        "Primary Source": ["Official MCX market watch", "Converted yfinance fallback", "Yahoo Finance", "Investing.com commodities", "1 second for live sources", "Estimated (Greeks)"],
        "Fallback": ["Converted global futures", "Yahoo Finance", "Yahoo Finance", "Yahoo Finance", "Manual page refresh", "Estimated (Greeks)"]
    }
    
    st.dataframe(pd.DataFrame(data_sources), use_container_width=True)
    
    st.success("""
    ### ⚡ Benefits:
    - **📊 Official MCX commodity quotes** - Directly from MCX market watch
    - **🔐 No broker token required** - No Dhan client id or access token
    - **🔄 1-second polling** - Dashboard reruns while MCX refresh is enabled
    - **🛟 Fallback retained** - Converted global futures are still available if MCX blocks the request
    """)
    
    st.warning("""
    ### ⚠️ Notes:
    - Official public web endpoints can change or rate-limit requests
    - Exchange-grade tick data still requires an authorized data-feed subscription
    - Option premiums estimated using model
    """)

# ============ TAB 7: TARGET PRICE FORECAST ============

with tab7:
    st.markdown("## 🎯 Fixed-Interval Target Price Forecast")
    st.caption(
        "Live commodity price beside expected target prices for 15, 30, 45 minutes, "
        "1 hour, and 2-5 hours. Forecasts refresh every second when the sidebar toggle is enabled."
    )

    forecast_rows = []
    detail_rows = []
    status_rows = []

    for commodity_key, (commodity_label, commodity_currency, commodity_yf_ticker) in COMMODITY_FORECAST_ASSETS.items():
        forecast_history = fetch_forecast_history(commodity_yf_ticker, commodity_key)
        if forecast_history.empty:
            status_rows.append({
                "Commodity": commodity_label,
                "Status": "No candle history available",
            })
            continue

        forecast_close_col = "Close" if "Close" in forecast_history.columns else "Adj Close"
        forecast_volume_col = "Volume" if "Volume" in forecast_history.columns else None

        live_quote = get_forecast_live_quote(commodity_key, commodity_yf_ticker)
        if commodity_key.startswith("MCX"):
            forecast_history = apply_live_mcx_quote(forecast_history, live_quote)
            forecast_currency = "₹"
        else:
            forecast_history = apply_live_global_quote(forecast_history, live_quote)
            forecast_currency = commodity_currency

        forecast_history = add_forecast_indicators(forecast_history, forecast_close_col)
        live_price = (
            float(live_quote["price"])
            if live_quote and live_quote.get("price") is not None
            else float(forecast_history[forecast_close_col].iloc[-1])
        )
        sentiment_for_forecast = get_forecast_sentiment(commodity_label)

        forecast_result = build_target_price_forecast(
            forecast_history,
            live_price,
            close_col=forecast_close_col,
            volume_col=forecast_volume_col,
            sentiment_data=sentiment_for_forecast,
            intervals=FORECAST_INTERVALS,
        )

        if not forecast_result.get("rows"):
            status_rows.append({
                "Commodity": commodity_label,
                "Status": forecast_result.get("message", "Forecast unavailable"),
            })
            continue

        summary_row = {
            "Commodity": commodity_label,
            "Live Price": format_forecast_price(live_price, forecast_currency),
            "Bias": forecast_result.get("signal", "NEUTRAL"),
            "Confidence": f"{forecast_result.get('confidence', 0):.0f}%",
            "Pattern": forecast_result.get("pattern", {}).get("current_pattern", "NO_PATTERN"),
            "Volume": forecast_result.get("volume", {}).get("anomaly_type", "UNAVAILABLE"),
            "Open Interest": forecast_result.get("open_interest", {}).get("oi_trend", "UNAVAILABLE"),
            "News": forecast_result.get("sentiment", {}).get("sentiment_label", "NEUTRAL"),
            "Updated": datetime.now().strftime("%H:%M:%S"),
        }

        for row in forecast_result["rows"]:
            interval_label = row["Interval"]
            summary_row[f"{interval_label} Forecast"] = format_forecast_price(
                row["Forecast Expected Price"],
                forecast_currency,
            )
            detail_rows.append({
                "Commodity": commodity_label,
                "Interval": interval_label,
                "Live Price": format_forecast_price(row["Current Price"], forecast_currency),
                "Forecast Expected Price": format_forecast_price(row["Forecast Expected Price"], forecast_currency),
                "Expected Change %": f"{row['Expected Change %']:+.2f}%",
                "Direction": row["Direction"],
                "Confidence": f"{row['Confidence %']:.0f}%",
            })

        forecast_rows.append(summary_row)

    if forecast_rows:
        st.subheader("All Commodities Forecast Grid")
        interval_columns = [f"{label} Forecast" for label, _ in FORECAST_INTERVALS]
        base_columns = [
            "Commodity",
            "Live Price",
            *interval_columns,
            "Bias",
            "Confidence",
            "Pattern",
            "Volume",
            "Open Interest",
            "News",
            "Updated",
        ]
        forecast_df = pd.DataFrame(forecast_rows)
        display_columns = [col for col in base_columns if col in forecast_df.columns]
        st.dataframe(forecast_df[display_columns], use_container_width=True, hide_index=True)

        st.subheader("Current vs Forecast by Interval")
        st.dataframe(pd.DataFrame(detail_rows), use_container_width=True, hide_index=True)

    if status_rows:
        st.warning("Some commodity forecasts could not be generated from the current data source.")
        st.dataframe(pd.DataFrame(status_rows), use_container_width=True, hide_index=True)

    st.info(
        "The model checks candle-pattern direction, support/resistance, recent momentum, "
        "volume spikes, available open interest fields, and commodity news sentiment. "
        "Open interest is marked unavailable when the upstream commodity feed does not provide it."
    )

st.markdown("---")
st.markdown("*⚠️ **DISCLAIMER**: This is an educational tool for analysis. Not financial advice. Always consult a professional advisor before trading. Past performance doesn't guarantee future results.*")

if (asset_name.startswith("MCX") and mcx_live_refresh) or \
   (asset_name in ["NIFTY", "SENSEX", "BANKNIFTY"] and nse_live_refresh) or \
   (asset_name in ["GC=F", "CL=F", "SI=F", "NG=F", "HG=F", "ZW=F", "ZS=F"] and global_live_refresh) or \
   target_forecast_refresh:
    time.sleep(1)
    st.rerun()
