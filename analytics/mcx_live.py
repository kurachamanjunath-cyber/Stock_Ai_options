"""Official MCX market-watch polling helpers."""
import json
import re
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
import requests


MCX_MARKET_WATCH_PAGE = "https://www.mcxindia.com/market-data/market-watch"
MCX_MARKET_WATCH_API = "https://www.mcxindia.com/backpage.aspx/GetMarketWatch"

MCX_ASSET_TO_COMMODITY = {
    "MCXGOLD": "GOLD",
    "MCXSILVER": "SILVER",
    "MCXNATURALGAS": "NATURALGAS",
    "MCXCRUDE": "CRUDEOIL",
    "MCXCOPPER": "COPPER",
    "MCXZINC": "ZINC",
    "MCXLEAD": "LEAD",
}


def _headers() -> Dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Content-Length": "0",
        "Content-Type": "application/json",
        "Origin": "https://www.mcxindia.com",
        "Referer": MCX_MARKET_WATCH_PAGE,
        "Sec-GPC": "1",
        "X-Requested-With": "XMLHttpRequest",
        "sec-ch-ua": '"Chromium";v="118", "Brave";v="118", "Not=A?Brand";v="99"',
        "sec-ch-ua-platform": '"Windows"',
    }


def _to_records(payload) -> List[Dict]:
    if isinstance(payload, dict) and "d" in payload:
        payload = payload["d"]

    if isinstance(payload, str):
        payload = payload.strip()
        if not payload:
            return []
        payload = json.loads(payload)

    if isinstance(payload, dict):
        for key in ("Data", "data", "Table", "table", "MarketWatch", "marketWatch"):
            if isinstance(payload.get(key), list):
                return payload[key]
        if all(not isinstance(value, (dict, list)) for value in payload.values()):
            return [payload]

    if isinstance(payload, list):
        return payload

    return []


def _find_value(row: Dict, candidates: List[str]):
    normalized = {
        re.sub(r"[^a-z0-9]", "", str(key).lower()): value
        for key, value in row.items()
    }
    for candidate in candidates:
        key = re.sub(r"[^a-z0-9]", "", candidate.lower())
        if key in normalized:
            return normalized[key]
    return None


def _number(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text in {"-", "--"}:
        return None
    text = text.replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None


def _commodity_text(row: Dict) -> str:
    parts = [
        _find_value(row, ["Commodity", "Symbol", "Product", "Instrument", "InstrumentName"]),
        _find_value(row, ["Instrument Identifier", "InstrumentIdentifier", "Contract"]),
    ]
    return " ".join(str(part) for part in parts if part is not None).upper().replace(" ", "")


def _is_futures_row(row: Dict) -> bool:
    option_type = str(_find_value(row, ["Option Type", "OptionType"]) or "").strip().upper()
    strike = str(_find_value(row, ["Strike Price", "StrikePrice"]) or "").strip()
    instrument = str(_find_value(row, ["Instrument", "InstrumentName"]) or "").upper()
    return (instrument in {"FUTCOM", "FUTIDX"}) or (
        not instrument.startswith("OPT")
        and option_type in {"", "-", "XX"}
        and strike in {"", "-", "0", "0.0", "0.00"}
    )


def _expiry(row: Dict):
    value = _find_value(row, ["Expiry Date", "ExpiryDate", "Expiry"])
    return pd.to_datetime(value, errors="coerce", dayfirst=True)


def fetch_mcx_market_watch() -> List[Dict]:
    session = requests.Session()
    session.trust_env = False
    headers = _headers()
    response = session.post(MCX_MARKET_WATCH_API, headers=headers, data={}, timeout=8)
    response.raise_for_status()
    return _to_records(response.json())


def get_live_mcx_quote(asset_name: str) -> Optional[Dict]:
    commodity = MCX_ASSET_TO_COMMODITY.get(asset_name)
    if not commodity:
        return None

    rows = fetch_mcx_market_watch()
    matches = []
    exact_matches = []
    for row in rows:
        symbol = str(_find_value(row, ["Symbol"]) or "").strip().upper()
        text = _commodity_text(row)
        ltp = _number(_find_value(row, ["LTP", "Last Traded Price", "LastTradedPrice", "LastPrice"]))
        if symbol == commodity and _is_futures_row(row) and ltp and ltp > 0:
            exact_matches.append(row)
        elif commodity in text and _is_futures_row(row) and ltp and ltp > 0:
            matches.append(row)

    if exact_matches:
        matches = exact_matches

    if not matches:
        return None

    matches.sort(key=lambda row: (_expiry(row) is pd.NaT, _expiry(row)))
    row = matches[0]

    price = _number(_find_value(row, ["LTP", "Last Traded Price", "LastTradedPrice", "LastPrice"]))
    if price is None:
        return None

    return {
        "price": price,
        "open": _number(_find_value(row, ["Open"])),
        "high": _number(_find_value(row, ["High"])),
        "low": _number(_find_value(row, ["Low"])),
        "close": _number(_find_value(row, ["Close", "Previous Close", "PreviousClose", "Prev Close"])),
        "volume": _number(_find_value(row, ["Vol (Lots)", "Volume", "Volume Lots", "VolLots"])),
        "change": _number(_find_value(row, ["Abs. Chng", "Abs Chng", "AbsoluteChange", "Change"])),
        "change_pct": _number(_find_value(row, ["% Change", "Percent Change", "PercentChange", "Change %"])),
        "expiry": _find_value(row, ["Expiry Date", "ExpiryDate", "Expiry"]),
        "commodity": commodity,
        "source": "MCX market watch",
        "timestamp": datetime.now(),
    }
