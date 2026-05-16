"""Live global futures and options data fetching."""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Optional
import time
import requests

class GlobalLiveData:
    """Fetch live global futures data."""

    # Mapping of global tickers to better APIs
    TICKER_MAPPING = {
        "GC=F": {"name": "Gold Futures", "api": "yfinance"},
        "CL=F": {"name": "Crude Oil Futures", "api": "yfinance"},
        "SI=F": {"name": "Silver Futures", "api": "yfinance"},
        "NG=F": {"name": "Natural Gas Futures", "api": "yfinance"},
        "HG=F": {"name": "Copper Futures", "api": "yfinance"},
        "ZW=F": {"name": "Wheat Futures", "api": "yfinance"},
        "ZS=F": {"name": "Soybean Futures", "api": "yfinance"},
    }

    def __init__(self):
        self.last_fetch = {}
        self.cache = {}
        self.cache_timeout = 1  # 1 second cache

    def get_live_futures_quote(self, ticker: str) -> Optional[Dict]:
        """
        Get live futures quote with 1-second refresh capability.

        Args:
            ticker: Yahoo Finance ticker symbol

        Returns:
            Dict with live price data or None if failed
        """
        try:
            # Check cache
            now = time.time()
            if ticker in self.cache and (now - self.last_fetch.get(ticker, 0)) < self.cache_timeout:
                return self.cache[ticker]

            # Fetch fresh data
            data = yf.download(ticker, period="1d", interval="1m", progress=False)

            if data.empty:
                return None

            latest = data.iloc[-1]
            prev_close = data.iloc[-2]["Close"] if len(data) > 1 else latest["Close"]

            result = {
                "symbol": ticker,
                "price": float(latest["Close"]),
                "change": float(latest["Close"] - prev_close),
                "change_percent": float((latest["Close"] - prev_close) / prev_close * 100) if prev_close != 0 else 0,
                "open": float(latest["Open"]),
                "high": float(latest["High"]),
                "low": float(latest["Low"]),
                "volume": int(latest["Volume"]) if "Volume" in data.columns else 0,
                "timestamp": datetime.now(),
                "source": "Yahoo Finance Live"
            }

            # Cache result
            self.cache[ticker] = result
            self.last_fetch[ticker] = now

            return result

        except Exception as e:
            print(f"Error fetching global live data for {ticker}: {e}")
            return None

    def get_live_options_quote(self, underlying: str, strike: float, option_type: str, expiry: str) -> Optional[Dict]:
        """
        Get live options quote for global markets.

        Args:
            underlying: Underlying ticker
            strike: Strike price
            option_type: 'CALL' or 'PUT'
            expiry: Expiry date YYYY-MM-DD

        Returns:
            Dict with options data
        """
        try:
            # Create options ticker
            expiry_short = datetime.strptime(expiry, "%Y-%m-%d").strftime("%y%m%d")
            option_ticker = f"{underlying}{expiry_short}{option_type[0]}{strike:08.0f}"

            data = yf.download(option_ticker, period="1d", progress=False)

            if data.empty:
                return None

            latest = data.iloc[-1]

            return {
                "symbol": option_ticker,
                "price": float(latest["Close"]),
                "bid": float(latest.get("Low", latest["Close"])),
                "ask": float(latest.get("High", latest["Close"])),
                "volume": int(latest.get("Volume", 0)),
                "open_interest": 0,  # Not available from yfinance
                "timestamp": datetime.now(),
                "source": "Yahoo Finance"
            }

        except Exception as e:
            print(f"Error fetching options data for {underlying}: {e}")
            return None

# Global instance
global_client = GlobalLiveData()

def get_live_global_quote(ticker: str) -> Optional[Dict]:
    """
    Get live global futures quote.

    Args:
        ticker: Yahoo Finance ticker symbol

    Returns:
        Dict with live data or None
    """
    return global_client.get_live_futures_quote(ticker)

def get_live_global_options_quote(underlying: str, strike: float, option_type: str, expiry: str) -> Optional[Dict]:
    """
    Get live global options quote.

    Args:
        underlying: Underlying ticker
        strike: Strike price
        option_type: 'CALL' or 'PUT'
        expiry: Expiry date

    Returns:
        Dict with options data
    """
    return global_client.get_live_options_quote(underlying, strike, option_type, expiry)