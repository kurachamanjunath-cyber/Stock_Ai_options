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
                                if item.get("indexName") == nse_index:
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
            return {
                "symbol": data.get("indexName", ""),
                "price": float(data.get("lastPrice", 0)),
                "change": float(data.get("change", 0)),
                "change_percent": float(data.get("pChange", 0)),
                "open": float(data.get("openPrice", 0)),
                "high": float(data.get("dayHigh", 0)),
                "low": float(data.get("dayLow", 0)),
                "volume": int(data.get("totalTradedVolume", 0)),
                "timestamp": datetime.now(),
                "source": "NSE Live"
            }
        except Exception as e:
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