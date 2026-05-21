"""Live global futures and options data fetching."""
import html
import re
import random
from io import StringIO

import yfinance as yf
import pandas as pd
from datetime import datetime
from typing import Dict, Optional
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

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
        """Fetch and briefly cache the Investing.com commodities page using Playwright."""
        now = time.time()
        if self.page_cache and (now - self.page_last_fetch) < self.cache_timeout:
            return self.page_cache

        # Try Playwright first (real browser, best for Cloudflare)
        if HAS_PLAYWRIGHT:
            # Try Firefox first (better anti-bot evasion), then Chromium
            browsers_to_try = [
                ('firefox', lambda p: p.firefox),
                ('chromium', lambda p: p.chromium),
            ]
            
            for browser_name, browser_getter in browsers_to_try:
                try:
                    with sync_playwright() as p:
                        browser_obj = browser_getter(p)
                        browser = browser_obj.launch(headless=True)
                        context = browser.new_context(
                            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
                            viewport={"width": 1920, "height": 1080},
                            locale="en-IN",
                            timezone_id="Asia/Kolkata"
                        )
                        page = context.new_page()
                        
                        try:
                            # Navigate with a 15 second timeout and domcontentloaded
                            page.goto(self.INVESTING_COMMODITIES_URL, wait_until="domcontentloaded", timeout=15000)
                            # Give JS time to render
                            page.wait_for_timeout(2000)
                            
                            html_content = page.content()
                            browser.close()
                            
                            if html_content and len(html_content) > 1000:
                                self.page_cache = html_content
                                self.page_last_fetch = now
                                print(f"✓ Fetched from Investing.com using {browser_name.upper()}")
                                return self.page_cache
                        except Exception as page_error:
                            browser.close()
                            # Try next browser
                            continue
                            
                except Exception as e:
                    # Try next browser
                    continue
                    
        # Multiple user agents to rotate
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
        ]
        
        user_agent = random.choice(user_agents)
        
        headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Ch-Ua": '"Not A(Brand";v="99", "Google Chrome";v="125"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Cache-Control": "max-age=0",
            "Referer": "https://www.investing.com/",
        }
        
        try:
            session = requests.Session()
            # Increase retry attempts for 403 errors
            retry_strategy = Retry(
                total=3,
                backoff_factor=1.0,  # Increase backoff delay
                status_forcelist=[403, 429, 500, 502, 503, 504],
                allowed_methods=["GET"]
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            
            # Add a small delay to avoid rate limiting
            time.sleep(random.uniform(0.5, 1.5))
            
            response = session.get(
                self.INVESTING_COMMODITIES_URL,
                headers=headers,
                timeout=15,
                allow_redirects=True,
                verify=True
            )
            response.raise_for_status()
            if response.status_code == 200:
                self.page_cache = response.text
                self.page_last_fetch = now
                print("✓ Fetched from Investing.com using requests")
                return self.page_cache
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                print(f"[Investing.com] 403 Forbidden - Site may have stricter Cloudflare protection")
            else:
                print(f"[Investing.com] HTTP Error {e.response.status_code}")
        except Exception as e:
            print(f"[Investing.com] Connection failed: {str(e)[:80]}")
        
        return None

    def _parse_investing_tables(self, page_html: str, investing_name: str) -> Optional[Dict]:
        """Read Investing.com commodity rows with pandas when table parsers are available."""
        try:
            tables = pd.read_html(StringIO(page_html))
        except Exception:
            return None

        for table in tables:
            # Try parsing standard format with columns like "Name", "Last", etc
            if "Name" in table.columns and "Last" in table.columns:
                rows = table[table["Name"].astype(str).str.contains(investing_name, case=False, regex=False)]
                if not rows.empty:
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

            # Try parsing compact format: [Name|Time, Price-Change-ChangePercent]
            if len(table.columns) >= 2:
                col0 = table.columns[0]
                col1 = table.columns[1]
                
                for _, row in table.iterrows():
                    try:
                        name_cell = str(row.get(col0, ""))
                        data_cell = str(row.get(col1, ""))
                        
                        # Check if name matches (e.g., "Gold23:41:44|GC")
                        if investing_name.lower() not in name_cell.lower():
                            continue
                        
                        # Parse price data: "4,547.75-10.25-0.22"
                        parts = data_cell.replace(",", "").split("-")
                        if len(parts) >= 3:
                            price = self._parse_number(parts[0])
                            if price is None:
                                continue
                            
                            change = self._parse_number(parts[1])
                            # Handle case where change might be negative
                            if len(parts) > 2 and parts[2] and parts[2][0].isdigit():
                                change_percent_str = parts[2]
                            else:
                                change_percent_str = None
                            
                            change_percent = self._parse_number(change_percent_str) if change_percent_str else 0.0
                            
                            return {
                                "price": price,
                                "previous": price + (change or 0) if change else price,
                                "high": None,
                                "low": None,
                                "change": change or 0.0,
                                "change_percent": change_percent or 0.0,
                                "market_time": "",
                            }
                    except Exception:
                        continue

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
        """Get a live global commodity quote from Investing.com India.
        
        Note: Investing.com has strong anti-scraping protection. This method will
        return None and the system will fall back to Yahoo Finance automatically.
        """
        mapping = self.TICKER_MAPPING.get(ticker, {})
        investing_name = mapping.get("investing_name")
        if not investing_name:
            return None

        try:
            page_html = self._get_investing_html()
            if not page_html:
                # Silently return None so fallback to Yahoo Finance happens
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
            # Silently fail so fallback happens
            return None

    def get_live_futures_quote(self, ticker: str) -> Optional[Dict]:
        """
        Get live futures quote with 1-second refresh capability.
        
        Attempts to fetch from Investing.com first, then falls back to Yahoo Finance.

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

            # Try Investing.com first
            investing_quote = self.get_investing_commodities_quote(ticker)
            if investing_quote:
                self.cache[ticker] = investing_quote
                self.last_fetch[ticker] = now
                return investing_quote

            # Fallback to Yahoo Finance if Investing.com fails
            return self._get_yfinance_fallback(ticker)

        except Exception as e:
            print(f"Error fetching global live data for {ticker}: {e}")
            # Try Yahoo Finance as last resort even if exception occurred
            try:
                return self._get_yfinance_fallback(ticker)
            except Exception as fallback_error:
                print(f"Yahoo Finance fallback also failed for {ticker}: {fallback_error}")
                return None

    def _get_yfinance_fallback(self, ticker: str) -> Optional[Dict]:
        """
        Fallback to Yahoo Finance when Investing.com fails.
        
        Args:
            ticker: Yahoo Finance ticker symbol
            
        Returns:
            Dict with live price data or None if failed
        """
        try:
            now = time.time()
            
            # Fetch fresh data from Yahoo Finance
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
                "source": "Yahoo Finance (Fallback)"
            }

            # Cache result
            self.cache[ticker] = result
            self.last_fetch[ticker] = now

            return result

        except Exception as e:
            print(f"Yahoo Finance fallback failed for {ticker}: {e}")
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
