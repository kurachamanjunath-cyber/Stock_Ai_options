#!/usr/bin/env python3
"""Simple polling script to stream live quotes from Investing.com via analytics.live_global.

Usage:
  python3 live_investing_stream.py NG=F  # default 10 samples every 1s
  python3 live_investing_stream.py NG=F 30  # 30 samples
"""
import sys
import time
import json
from datetime import datetime

from analytics.live_global import get_live_global_quote


def format_price(p):
    try:
        v = float(p)
        if abs(v) < 10:
            return f"{v:,.3f}"
        return f"{v:,.2f}"
    except Exception:
        return "N/A"


def main():
    ticker = sys.argv[1] if len(sys.argv) > 1 else "NG=F"
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    interval = 1.0

    print(f"Streaming {ticker} from Investing.com ({count} samples, {interval}s interval)")
    for i in range(count):
        q = get_live_global_quote(ticker)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if q and q.get("price") is not None:
            print(f"{ts} | {ticker} | price={format_price(q['price'])} | change={format_price(q.get('change',0))} | src={q.get('source')}")
        else:
            print(f"{ts} | {ticker} | no quote (fallback to yfinance may be used)")
        time.sleep(interval)


if __name__ == "__main__":
    main()
