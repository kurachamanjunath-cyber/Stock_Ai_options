"""Live NSE data fetching for Indian indices."""
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Optional
import time
import json

class NSELiveData:
    """Fetch live NSE index data."""

    BASE_URL = "https://www.nseindia.com/api"
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.nseindia.com/',
    }

    INDEX_MAPPING = {
        "NIFTY": "NIFTY 50",
        "SENSEX": "SENSEX",
        "BANKNIFTY": "NIFTY BANK"
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        # Initialize session with NSE
        self._init_session()

    def _init_session(self):
        """Initialize session with NSE website."""
        try:
            # Visit main page to set cookies
            self.session.get("https://www.nseindia.com", timeout=10)
            time.sleep(1)  # Rate limiting
        except Exception as e:
            print(f"NSE session init failed: {e}")

    def get_live_index_quote(self, index_symbol: str) -> Optional[Dict]:
        """
        Get live quote for NSE index.

        Args:
            index_symbol: NIFTY, SENSEX, or BANKNIFTY

        Returns:
            Dict with live price data or None if failed
        """
        try:
            # Map to NSE API format
            nse_index = self.INDEX_MAPPING.get(index_symbol, index_symbol)

            # Try different API endpoints
            endpoints = [
                f"{self.BASE_URL}/equity-stockIndices?index={nse_index.replace(' ', '%20')}",
                f"{self.BASE_URL}/allIndices",
            ]

            for endpoint in endpoints:
                try:
                    response = self.session.get(endpoint, timeout=5)
                    response.raise_for_status()

                    data = response.json()

                    # Parse based on endpoint
                    if "equity-stockIndices" in endpoint:
                        if data.get("data"):
                            for item in data["data"]:
                                if item.get("indexName") == nse_index:
                                    return self._parse_index_data(item)
                    elif "allIndices" in endpoint:
                        if data.get("data"):
                            for item in data["data"]:
                                if item.get("indexName") == nse_index or item.get("index") == nse_index:
                                    return self._parse_index_data(item)

                except Exception as e:
                    continue

            # Fallback to yfinance if NSE API fails
            return self._get_yfinance_fallback(index_symbol)

        except Exception as e:
            print(f"Error fetching NSE live data for {index_symbol}: {e}")
            return self._get_yfinance_fallback(index_symbol)

    def _parse_index_data(self, data: Dict) -> Dict:
        """Parse NSE API response."""
        try:
            price = data.get("lastPrice", data.get("last", 0))
            change = data.get("change", data.get("variation", 0))
            change_percent = data.get("pChange", data.get("percentChange", 0))
            open_price = data.get("openPrice", data.get("open", 0))
            high = data.get("dayHigh", data.get("high", 0))
            low = data.get("dayLow", data.get("low", 0))
            volume = data.get("totalTradedVolume", data.get("volume", 0))

            return {
                "symbol": data.get("indexName", data.get("index", "")),
                "price": float(price),
                "change": float(change),
                "change_percent": float(change_percent),
                "open": float(open_price),
                "high": float(high),
                "low": float(low),
                "volume": int(float(volume or 0)),
                "timestamp": datetime.now(),
                "source": "NSE Live"
            }
        except Exception as e:
            return None

    def get_index_history(self, index_symbol: str) -> Optional[pd.DataFrame]:
        """
        Get NSE-provided index history points for forecast context.

        NSE's public allIndices endpoint provides current OHLC plus recent
        reference values. This is used as the primary NSE source; yfinance is
        only used by the caller when this endpoint is unavailable.
        """
        try:
            nse_index = self.INDEX_MAPPING.get(index_symbol, index_symbol)
            response = self.session.get(f"{self.BASE_URL}/allIndices", timeout=5)
            response.raise_for_status()
            payload = response.json()

            row = None
            for item in payload.get("data", []):
                if item.get("indexName") == nse_index or item.get("index") == nse_index:
                    row = item
                    break

            if not row:
                return None

            now = datetime.now()
            points = []
            dated_points = [
                ("date365dAgo", "oneYearAgoVal"),
                ("date30dAgo", "oneMonthAgoVal"),
                ("oneWeekAgo", "oneWeekAgoVal"),
                ("previousDay", "previousDayVal"),
            ]
            for date_key, value_key in dated_points:
                value = row.get(value_key)
                if value in (None, "", 0):
                    continue
                try:
                    date_value = pd.to_datetime(row.get(date_key), dayfirst=True, errors="coerce")
                    if pd.isna(date_value):
                        date_value = now - timedelta(days=len(dated_points) - len(points))
                    close = float(value)
                    points.append({
                        "DateTime": date_value,
                        "Open": close,
                        "High": close,
                        "Low": close,
                        "Close": close,
                        "Volume": 0,
                    })
                except Exception:
                    continue

            quote = self._parse_index_data(row)
            if quote and quote.get("price"):
                points.append({
                    "DateTime": now,
                    "Open": float(quote.get("open") or quote["price"]),
                    "High": float(quote.get("high") or quote["price"]),
                    "Low": float(quote.get("low") or quote["price"]),
                    "Close": float(quote["price"]),
                    "Volume": int(quote.get("volume") or 0),
                })

            if len(points) < 3:
                return None

            history = pd.DataFrame(points).drop_duplicates(subset=["DateTime"]).set_index("DateTime")
            history = history.sort_index()
            history.attrs["source"] = "NSE allIndices"
            return history
        except Exception:
            return None

    def _get_yfinance_fallback(self, index_symbol: str) -> Optional[Dict]:
        """Fallback to yfinance for NSE data."""
        try:
            import yfinance as yf

            ticker_map = {
                "NIFTY": "^NSEI",
                "SENSEX": "^BSESN",
                "BANKNIFTY": "^NSEBANK"
            }

            ticker = ticker_map.get(index_symbol)
            if not ticker:
                return None

            data = yf.download(ticker, period="1d", interval="1m", progress=False)
            if data.empty:
                return None

            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            latest = data.iloc[-1]
            prev_close = data.iloc[-2]["Close"] if len(data) > 1 else latest["Close"]

            return {
                "symbol": index_symbol,
                "price": float(latest["Close"]),
                "change": float(latest["Close"] - prev_close),
                "change_percent": float((latest["Close"] - prev_close) / prev_close * 100),
                "open": float(latest["Open"]),
                "high": float(latest["High"]),
                "low": float(latest["Low"]),
                "volume": int(latest["Volume"]) if "Volume" in data.columns else 0,
                "timestamp": datetime.now(),
                "source": "Yahoo Finance"
            }
        except Exception as e:
            return None

# Global instance
nse_client = NSELiveData()

def get_live_nse_quote(index_symbol: str) -> Optional[Dict]:
    """
    Get live NSE index quote.

    Args:
        index_symbol: NIFTY, SENSEX, or BANKNIFTY

    Returns:
        Dict with live data or None
    """
    return nse_client.get_live_index_quote(index_symbol)

def get_nse_index_history(index_symbol: str) -> Optional[pd.DataFrame]:
    """
    Get NSE index history points from nseindia.com.

    Args:
        index_symbol: NIFTY or BANKNIFTY

    Returns:
        DataFrame with OHLCV data or None
    """
    return nse_client.get_index_history(index_symbol)
