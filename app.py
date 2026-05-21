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
import time
import warnings
import json
import queue
import threading

try:
    import websocket
except ImportError:
    websocket = None

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
    from analytics.live_nse import get_live_nse_quote, get_nse_index_history
    from analytics.live_global import get_live_global_quote
    from analytics.target_price_forecast import FORECAST_INTERVALS, build_target_price_forecast
except ImportError as e:
    st.error(f"Analytics module error: {e}. Please ensure all files in analytics/ directory are created.")
    st.stop()

st.set_page_config(page_title="Advanced Intraday Options Predictor", layout="wide")

# ============ CONFIGURATION ============

st.title("📊 Advanced INTRADAY Options Predictor")
st.markdown("**INTRADAY CALL/PUT Signals → Today's Entry & Target Prices for MCX Commodities, NSE Indices & Global Futures**")
st.markdown(
    """
    <style>
    /* Keep live forecast values visible while Streamlit refreshes fragments. */
    [data-testid="stApp"][data-test-script-state="running"] [data-testid="stElementContainer"],
    [data-testid="stApp"][data-test-script-state="running"] [data-testid="stVerticalBlock"],
    [data-testid="stApp"][data-test-script-state="running"] [data-testid="stDataFrame"],
    [data-testid="stApp"] [class*="stale"],
    [data-testid="stApp"] [class*="Stale"],
    .stale-element {
        opacity: 1 !important;
        filter: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

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


def _initialize_ws_client(asset_name: str, yf_ticker: str):
    if websocket is None:
        return

    if "wsq" not in st.session_state:
        st.session_state.wsq = queue.Queue()
        st.session_state.ws_live_data = {}

    if "ws_thread" in st.session_state and st.session_state.ws_thread is not None:
        if st.session_state.ws_thread.is_alive():
            return

    def on_message(ws, message):
        try:
            payload = json.loads(message)
            st.session_state.wsq.put(payload)
        except Exception:
            st.session_state.wsq.put({"raw": message})

    def on_open(ws):
        # Subscribe to the selected instrument for live streaming
        if asset_name.startswith("MCX"):
            subscribe = [f"mcx:{asset_name}"]
        elif asset_name in ["NIFTY", "SENSEX", "BANKNIFTY"]:
            subscribe = [f"nse:{asset_name}"]
        else:
            subscribe = [f"global:{yf_ticker}"]

        ws.send(json.dumps({"subscribe": subscribe, "interval": 1.0}))

    def run_ws():
        while True:
            try:
                ws = websocket.WebSocketApp(
                    "ws://127.0.0.1:8000/ws",
                    on_message=on_message,
                    on_open=on_open,
                )
                ws.run_forever()
            except Exception:
                time.sleep(5)

    st.session_state.ws_thread = threading.Thread(target=run_ws, daemon=True)
    st.session_state.ws_thread.start()


def _drain_ws_queue():
    if "wsq" not in st.session_state:
        return
    while True:
        try:
            item = st.session_state.wsq.get_nowait()
            if isinstance(item, dict) and item.get("type") == "update":
                st.session_state.ws_live_data.update(item.get("data", {}))
            elif isinstance(item, dict):
                st.session_state.ws_live_data.update(item)
        except queue.Empty:
            break


def _get_ws_quote(kind: str, symbol: str):
    if "ws_live_data" not in st.session_state:
        return None
    return st.session_state.ws_live_data.get(f"{kind.upper()}:{symbol}")

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
        nse_live_refresh = False
        global_live_refresh = False
        st.info("📌 **MCX DATA**: Using official MCX market-watch prices first; yfinance is fallback/history.")
    elif asset_name in ["NIFTY", "SENSEX", "BANKNIFTY"]:
        nse_live_refresh = st.toggle(
            "🔄 Refresh NSE live data every 1s",
            value=True,
            help="Polls NSE live data every second for real-time Indian index prices."
        )
        mcx_live_refresh = False
        global_live_refresh = False
        st.info("📌 **NSE DATA**: Using NSE live API with yfinance fallback for real-time index data.")
    elif asset_name in ["GC=F", "CL=F", "SI=F", "NG=F", "HG=F", "ZW=F", "ZS=F"]:
        global_live_refresh = st.toggle(
            "🔄 Refresh Global live data every 1s",
            value=True,
            help="Polls global futures data every second for real-time international prices."
        )
        mcx_live_refresh = False
        nse_live_refresh = False
        st.info("📌 **GLOBAL DATA**: Using Investing.com commodities first with yfinance fallback.")
    else:
        mcx_live_refresh = False
        nse_live_refresh = False
        global_live_refresh = False
    
    # Option pricing parameters
    st.markdown("---")
    st.subheader("⚡ Options Parameters")
    strike_interval = st.number_input("Strike Interval", value=100, step=50, min_value=1)
    
    # Fixed for intraday trading
    days_to_expiry = 1  # Intraday expiry (same day)

    # Start WebSocket live streaming for selected instrument
    _initialize_ws_client(asset_name, yf_ticker)

    if mcx_live_refresh or nse_live_refresh or global_live_refresh:
        st.markdown(
            '<script>setTimeout(() => { window.location.reload(); }, 1000);</script>',
            unsafe_allow_html=True,
        )

# ============ DATA FETCHING & PROCESSING ============

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


def fetch_live_mcx_quote(asset_name: str):
    """Fetch a fresh MCX quote from the official market-watch source."""
    _drain_ws_queue()
    ws_quote = _get_ws_quote("mcx", asset_name)
    if ws_quote and ws_quote.get("price") is not None:
        return ws_quote

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


def fetch_live_nse_quote(asset_name: str):
    """Fetch a fresh NSE index quote."""
    _drain_ws_queue()
    ws_quote = _get_ws_quote("nse", asset_name)
    if ws_quote and ws_quote.get("price") is not None:
        return ws_quote

    try:
        return get_live_nse_quote(asset_name)
    except Exception as e:
        return {"error": str(e), "source": "NSE API"}

def fetch_live_global_quote(asset_name: str):
    """Fetch a fresh global futures quote."""
    _drain_ws_queue()
    ws_quote = _get_ws_quote("global", asset_name)
    if ws_quote and ws_quote.get("price") is not None:
        return ws_quote

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


TARGET_FORECAST_ASSETS = {
    **ASSETS["🇮🇳 MCX Commodities"],
    **ASSETS["📊 NSE Index Options"],
    **ASSETS["🌍 Global Futures"],
}


@st.cache_data(ttl=300, show_spinner=False)
def fetch_forecast_history(yf_ticker: str, asset_key: str) -> pd.DataFrame:
    """Fetch short intraday candles for the fixed target-price forecast tab."""
    try:
        if yf_ticker == "LD=F":
            return pd.DataFrame()

        if asset_key in ["NIFTY", "BANKNIFTY"]:
            nse_history = get_nse_index_history(asset_key)
            if nse_history is not None and not nse_history.empty:
                return nse_history.tail(240)

        history = yf.download(yf_ticker, period="5d", interval="5m", progress=False)
        if history.empty:
            history = yf.download(yf_ticker, period="1mo", progress=False)

        if isinstance(history.columns, pd.MultiIndex):
            history.columns = history.columns.get_level_values(0)
        history.columns = history.columns.str.strip().str.title()

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


def rebase_history_to_live_price(
    history: pd.DataFrame,
    live_price: float,
    close_col_name: str = "Close"
) -> pd.DataFrame:
    """
    Rebase a related futures history to the selected live instrument price.

    MCX forecast rows use global futures candles for direction, but the displayed
    target must stay on the live MCX price scale. This keeps paired MCX/global
    forecasts directionally aligned without using USD/INR conversion logic.
    """
    if history.empty or close_col_name not in history.columns:
        return history

    latest_close = history[close_col_name].dropna().iloc[-1]
    if latest_close <= 0 or live_price <= 0:
        return history

    rebased = history.copy()
    factor = live_price / float(latest_close)
    for col in ["Open", "High", "Low", "Close", "Adj Close"]:
        if col in rebased.columns:
            rebased[col] = rebased[col] * factor

    return rebased


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
    """Fetch the live quote source appropriate for the target forecast table."""
    if asset_key.startswith("MCX"):
        return fetch_live_mcx_quote(asset_key) or {}
    if asset_key in ["NIFTY", "SENSEX", "BANKNIFTY"]:
        return fetch_live_nse_quote(asset_key) or {}
    return fetch_live_global_quote(yf_ticker) or {}


def format_forecast_price(value: float, currency_symbol: str) -> str:
    """Format forecast prices consistently inside dataframe rows."""
    try:
        return f"{currency_symbol}{float(value):,.2f}"
    except Exception:
        return f"{currency_symbol}0.00"


def format_price_dynamic(value: float, currency_symbol: str) -> str:
    """Format prices with higher precision for small-dollar instruments.

    - If price < 10, show 3 decimal places (e.g., 2.994)
    - Otherwise show 2 decimal places
    """
    try:
        v = float(value)
        if abs(v) < 10:
            return f"{currency_symbol}{v:,.3f}"
        return f"{currency_symbol}{v:,.2f}"
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
current_price = float(current_price_raw)
display_currency = currency

last_change = data["Daily Change"].iloc[-1]
sma_10 = data["SMA_10"].iloc[-1]
sma_20 = data["SMA_20"].iloc[-1]
rsi = data["RSI_14"].iloc[-1]
macd_val = data["MACD"].iloc[-1]
macd_signal = data["MACD_Signal"].iloc[-1]
volume_trend = data["Volume_Trend"].iloc[-1] if "Volume_Trend" in data.columns else 0

# ============ MAIN DISPLAY ============

# Current metrics
st.subheader(f"📊 {display_name} | Current Price: {format_price_dynamic(current_price, display_currency)}")
if asset_name.startswith("MCX"):
    if mcx_quote.get("price") is not None:
        quote_time = mcx_quote.get("timestamp") or datetime.now()
        expiry_text = f" | Expiry: {mcx_quote['expiry']}" if mcx_quote.get("expiry") else ""
        st.success(
            f"📡 Official MCX market-watch quote: {display_currency}{mcx_quote['price']:.2f}"
            f" | refreshed {quote_time.strftime('%H:%M:%S')}{expiry_text}"
        )
    elif mcx_quote.get("error"):
        st.warning(f"📡 MCX market-watch unavailable: {mcx_quote['error']}. Showing yfinance fallback/history.")
    else:
        st.warning("📡 MCX market-watch did not return a quote. Showing yfinance fallback/history.")
elif asset_name in ["NIFTY", "SENSEX", "BANKNIFTY"]:
    if nse_quote.get("price") is not None:
        quote_time = nse_quote.get("timestamp") or datetime.now()
        change_text = f" | Change: {nse_quote['change']:.2f} ({nse_quote['change_percent']:.2f}%)"
        st.success(
            f"📡 NSE Live quote: {format_price_dynamic(nse_quote['price'], display_currency)}{change_text}"
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
            f"📡 Global Live quote: {format_price_dynamic(global_quote['price'], display_currency)}{change_text}"
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
            st.markdown(f"**Current Price**\n# {format_price_dynamic(current_price, display_currency)}")
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
        - Price is at **{format_price_dynamic(current_price, display_currency)}**
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
        - Price is at **{format_price_dynamic(current_price, display_currency)}**
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
    yfinance as a fallback/history source.

    ### 📊 Data Sources Comparison:
    """)
    
    data_sources = {
        "Data Type": ["MCX Commodities", "MCX History", "NSE/BSE Indices", "Global Futures", "Refresh", "Options Premiums"],
        "Primary Source": ["Official MCX market watch", "yfinance fallback", "Yahoo Finance", "Investing.com commodities", "1 second for live sources", "Estimated (Greeks)"],
        "Fallback": ["Global futures history", "Yahoo Finance", "Yahoo Finance", "Yahoo Finance", "Manual page refresh", "Estimated (Greeks)"]
    }
    
    st.dataframe(pd.DataFrame(data_sources), use_container_width=True)
    
    st.success("""
    ### ⚡ Benefits:
    - **📊 Official MCX commodity quotes** - Directly from MCX market watch
    - **🔐 No broker token required** - No Dhan client id or access token
    - **🔄 1-second polling** - Dashboard reruns while MCX refresh is enabled
    - **🛟 Fallback retained** - Global futures history is still available if MCX blocks the request
    """)
    
    st.warning("""
    ### ⚠️ Notes:
    - Official public web endpoints can change or rate-limit requests
    - Exchange-grade tick data still requires an authorized data-feed subscription
    - Option premiums estimated using model
    """)

# ============ TAB 7: TARGET PRICE FORECAST ============

def render_target_price_forecast():
    """Render target-price forecasts inside a Streamlit fragment."""
    forecast_rows = []
    status_rows = []

    for asset_key, (asset_label, asset_currency, asset_yf_ticker) in TARGET_FORECAST_ASSETS.items():
        forecast_history = fetch_forecast_history(asset_yf_ticker, asset_key)
        if forecast_history.empty:
            status_rows.append({
                "Instrument": asset_label,
                "Status": "No candle history available",
            })
            continue

        forecast_close_col = "Close" if "Close" in forecast_history.columns else "Adj Close"
        forecast_volume_col = "Volume" if "Volume" in forecast_history.columns else None

        live_quote = get_forecast_live_quote(asset_key, asset_yf_ticker)
        live_price = (
            float(live_quote["price"])
            if live_quote and live_quote.get("price") is not None
            else float(forecast_history[forecast_close_col].iloc[-1])
        )

        if asset_key.startswith("MCX"):
            forecast_history = rebase_history_to_live_price(
                forecast_history,
                live_price,
                forecast_close_col,
            )
            forecast_history = apply_live_mcx_quote(forecast_history, live_quote)
            forecast_currency = "₹"
        elif asset_key in ["NIFTY", "SENSEX", "BANKNIFTY"]:
            forecast_history = apply_live_nse_quote(forecast_history, live_quote)
            forecast_currency = "₹"
        else:
            forecast_history = apply_live_global_quote(forecast_history, live_quote)
            forecast_currency = asset_currency

        forecast_history = add_forecast_indicators(forecast_history, forecast_close_col)
        sentiment_for_forecast = get_forecast_sentiment(asset_label)

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
                "Instrument": asset_label,
                "Status": forecast_result.get("message", "Forecast unavailable"),
            })
            continue

        summary_row = {
            "Instrument": asset_label,
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

        forecast_rows.append(summary_row)

    if forecast_rows:
        st.subheader("All Instruments Forecast Grid")
        interval_columns = [f"{label} Forecast" for label, _ in FORECAST_INTERVALS]
        base_columns = [
            "Instrument",
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
        st.dataframe(forecast_df[display_columns], width="stretch", hide_index=True)

    if status_rows:
        st.warning("Some instrument forecasts could not be generated from the current data source.")
        st.dataframe(pd.DataFrame(status_rows), width="stretch", hide_index=True)

    st.info(
        "The model checks candle-pattern direction, support/resistance, recent momentum, "
        "volume spikes, available open interest fields, and instrument news sentiment. "
        "Open interest is marked unavailable when the upstream feed does not provide it."
    )


@st.fragment(run_every="1s")
def render_live_target_price_forecast():
    """Refresh only the target forecast section in the background."""
    render_target_price_forecast()


with tab7:
    st.markdown("## 🎯 Fixed-Interval Target Price Forecast")
    st.caption(
        "Live instrument price beside expected target prices for 15, 30, 45 minutes, "
        "1 hour, and 2-5 hours. Forecasts refresh in the background when the sidebar toggle is enabled."
    )

    if target_forecast_refresh:
        render_live_target_price_forecast()
    else:
        render_target_price_forecast()

st.markdown("---")
st.markdown("*⚠️ **DISCLAIMER**: This is an educational tool for analysis. Not financial advice. Always consult a professional advisor before trading. Past performance doesn't guarantee future results.*")

if not target_forecast_refresh and (
    (asset_name.startswith("MCX") and mcx_live_refresh) or
    (asset_name in ["NIFTY", "SENSEX", "BANKNIFTY"] and nse_live_refresh) or
    (asset_name in ["GC=F", "CL=F", "SI=F", "NG=F", "HG=F", "ZW=F", "ZS=F"] and global_live_refresh)
):
    time.sleep(1)
    st.rerun()
