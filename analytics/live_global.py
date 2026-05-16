"""Live global futures and options data fetching."""
import html
import re
from io import StringIO

import yfinance as yf
import pandas as pd
from datetime import datetime
from typing import Dict, Optional
import time
import requests

class GlobalLiveData:
    """Fetch live global futures data."""

    # Mapping of global tickers to better APIs
    TICKER_MAPPING = {
        "GC=F": {"name": "Gold Futures", "investing_name": "Gold", "api": "investing"},
        "CL=F": {"name": "Crude Oil Futures", "investing_name": "Crude Oil WTI", "api": "investing"},
        "SI=F": {"name": "Silver Futures", "investing_name": "Silver", "api": "investing"},
        "NG=F": {"name": "Natural Gas Futures", "investing_name": "Natural Gas", "api": "investing"},
        "HG=F": {"name": "Copper Futures", "investing_name": "Copper", "api": "investing"},
        "ZW=F": {"name": "Wheat Futures", "api": "yfinance"},
        "ZS=F": {"name": "Soybean Futures", "api": "yfinance"},
    }
    INVESTING_COMMODITIES_URL = "https://in.investing.com/commodities"

    def __init__(self):
        self.last_fetch = {}
        self.cache = {}
        self.cache_timeout = 1  # 1 second cache
        self.page_cache = None
        self.page_last_fetch = 0

    @staticmethod
    def _parse_number(value) -> Optional[float]:
        """Parse Investing.com formatted numeric strings."""
        try:
            if value is None:
                return None
            text = str(value).strip().replace(",", "").replace("%", "")
            if not text or text in {"-", "--"}:
                return None
            return float(text)
        except Exception:
            return None

    def _get_investing_html(self) -> Optional[str]:
        """Fetch and briefly cache the Investing.com commodities page."""
        now = time.time()
        if self.page_cache and (now - self.page_last_fetch) < self.cache_timeout:
            return self.page_cache

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
            "Referer": "https://in.investing.com/",
        }
        response = requests.get(self.INVESTING_COMMODITIES_URL, headers=headers, timeout=8)
        response.raise_for_status()
        self.page_cache = response.text
        self.page_last_fetch = now
        return self.page_cache

    def _parse_investing_tables(self, page_html: str, investing_name: str) -> Optional[Dict]:
        """Read Investing.com commodity rows with pandas when table parsers are available."""
        try:
            tables = pd.read_html(StringIO(page_html))
        except Exception:
            return None

        for table in tables:
            if "Name" not in table.columns or "Last" not in table.columns:
                continue

            rows = table[table["Name"].astype(str).str.contains(investing_name, case=False, regex=False)]
            if rows.empty:
                continue

            row = rows.iloc[0]
            price = self._parse_number(row.get("Last"))
            if price is None:
                continue

            previous = self._parse_number(row.get("Prev."))
            change = self._parse_number(row.get("Chg."))
            change_percent = self._parse_number(row.get("Chg. %"))
            if change is None and previous not in (None, 0):
                change = price - previous
            if change_percent is None and previous not in (None, 0):
                change_percent = (price - previous) / previous * 100

            return {
                "price": price,
                "previous": previous,
                "high": self._parse_number(row.get("High")),
                "low": self._parse_number(row.get("Low")),
                "change": change or 0.0,
                "change_percent": change_percent or 0.0,
                "market_time": str(row.get("Time", "")).strip(),
            }

        return None

    def _parse_investing_text(self, page_html: str, investing_name: str) -> Optional[Dict]:
        """Fallback parser for the rendered text shape of Investing.com commodity rows."""
        text = re.sub(r"<script\b[^>]*>.*?</script>", " ", page_html, flags=re.I | re.S)
        text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
        text = html.unescape(re.sub(r"<[^>]+>", "\n", text))
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        row_pattern = re.compile(
            r"(?P<month>[A-Z][a-z]{2}\s+\d{2})\s+"
            r"(?P<last>-?[\d,]+(?:\.\d+)?)\s+"
            r"(?P<prev>-?[\d,]+(?:\.\d+)?)\s+"
            r"(?P<high>-?[\d,]+(?:\.\d+)?)\s+"
            r"(?P<low>-?[\d,]+(?:\.\d+)?)\s*"
            r"(?P<chg>[+-]?[\d,]+(?:\.\d+)?)\s*"
            r"(?P<chg_pct>[+-]?[\d,]+(?:\.\d+)?)%\s*"
            r"(?P<time>\d{2}:\d{2}:\d{2}|\d{1,2}/\d{1,2})",
        )

        row_match = None
        for idx, line in enumerate(lines):
            if not line.lower().startswith(investing_name.lower()):
                continue
            row_text = " ".join(lines[idx + 1:idx + 8])
            row_match = row_pattern.search(row_text)
            if row_match:
                break

        if not row_match:
            return None

        previous = self._parse_number(row_match.group("prev"))
        price = self._parse_number(row_match.group("last"))
        if price is None:
            return None

        return {
            "price": price,
            "previous": previous,
            "high": self._parse_number(row_match.group("high")),
            "low": self._parse_number(row_match.group("low")),
            "change": self._parse_number(row_match.group("chg")) or 0.0,
            "change_percent": self._parse_number(row_match.group("chg_pct")) or 0.0,
            "market_time": row_match.group("time"),
        }

    def get_investing_commodities_quote(self, ticker: str) -> Optional[Dict]:
        """Get a live global commodity quote from Investing.com India."""
        mapping = self.TICKER_MAPPING.get(ticker, {})
        investing_name = mapping.get("investing_name")
        if not investing_name:
            return None

        try:
            page_html = self._get_investing_html()
            if not page_html:
                return None

            quote = (
                self._parse_investing_tables(page_html, investing_name)
                or self._parse_investing_text(page_html, investing_name)
            )
            if not quote:
                return None

            return {
                "symbol": ticker,
                "price": float(quote["price"]),
                "change": float(quote.get("change", 0.0)),
                "change_percent": float(quote.get("change_percent", 0.0)),
                "open": None,
                "high": quote.get("high"),
                "low": quote.get("low"),
                "volume": 0,
                "timestamp": datetime.now(),
                "market_time": quote.get("market_time"),
                "source": "Investing.com India Commodities",
            }
        except Exception as e:
            self.cache[f"{ticker}:investing_error"] = str(e)
            return None

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

            investing_quote = self.get_investing_commodities_quote(ticker)
            if investing_quote:
                self.cache[ticker] = investing_quote
                self.last_fetch[ticker] = now
                return investing_quote

            # Fetch fresh data
            data = yf.download(ticker, period="1d", interval="1m", progress=False)

            if data.empty:
                return None

            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

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
                "source": "Yahoo Finance Live Fallback"
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

def get_live_investing_commodities_quote(ticker: str) -> Optional[Dict]:
    """
    Get a global commodity quote directly from Investing.com India.

    Args:
        ticker: Yahoo Finance-style commodity ticker used by the app

    Returns:
        Dict with live data or None
    """
    return global_client.get_investing_commodities_quote(ticker)

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
