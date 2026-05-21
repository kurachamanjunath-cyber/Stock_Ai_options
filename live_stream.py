#!/usr/bin/env python3
"""Unified live streamer for Global (Investing.com), NSE indices, and MCX commodities.

Usage examples:
  # Stream defaults (NG=F, NIFTY, MCXNATURALGAS) 10 samples
  python3 live_stream.py

  # Stream specific instruments for 20 samples every 1s
  python3 live_stream.py --instruments global:NG=F nse:NIFTY mcx:MCXNATURALGAS --count 20 --interval 1
"""
import argparse
import threading
import time
from datetime import datetime
from typing import Callable, Dict

from analytics.live_global import get_live_global_quote
from analytics.live_nse import get_live_nse_quote
from analytics.mcx_live import get_live_mcx_quote


def format_price(p: float) -> str:
    try:
        v = float(p)
        if abs(v) < 10:
            return f"{v:,.3f}"
        return f"{v:,.2f}"
    except Exception:
        return "N/A"


def stream_loop(name: str, fetcher: Callable[[str], Dict], symbol: str, count: int, interval: float):
    for i in range(count):
        try:
            q = fetcher(symbol)
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if q and q.get("price") is not None:
                print(f"{ts} | {name}:{symbol} | price={format_price(q['price'])} | change={format_price(q.get('change',0))} | src={q.get('source')}")
            else:
                print(f"{ts} | {name}:{symbol} | no quote")
        except Exception as e:
            print(f"{datetime.now().strftime('%H:%M:%S')} | {name}:{symbol} | error: {e}")
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instruments", nargs="*", help="List like global:NG=F nse:NIFTY mcx:MCXNATURALGAS", default=[])
    parser.add_argument("--count", type=int, default=10, help="Number of samples per instrument")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between samples")

    args = parser.parse_args()

    instruments = args.instruments
    if not instruments:
        instruments = ["global:NG=F", "nse:NIFTY", "mcx:MCXNATURALGAS"]

    threads = []
    for inst in instruments:
        if ":" not in inst:
            print(f"Invalid instrument format: {inst}. Expected type:symbol")
            continue
        kind, symbol = inst.split(":", 1)
        kind = kind.lower()
        if kind == "global":
            fetcher = get_live_global_quote
            name = "GLOBAL"
        elif kind == "nse":
            fetcher = get_live_nse_quote
            name = "NSE"
        elif kind == "mcx":
            fetcher = get_live_mcx_quote
            name = "MCX"
        else:
            print(f"Unknown kind: {kind}")
            continue

        t = threading.Thread(target=stream_loop, args=(name, fetcher, symbol, args.count, args.interval), daemon=True)
        threads.append(t)
        t.start()

    # Wait for threads to finish
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
