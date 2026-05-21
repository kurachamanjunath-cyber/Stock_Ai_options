#!/usr/bin/env python3
"""FastAPI WebSocket server that streams live quotes for Global/NSE/MCX.

Connect to ws://<host>:<port>/ws and optionally send a JSON subscribe message
immediately after connecting, e.g.

  {"subscribe": ["global:NG=F", "nse:NIFTY", "mcx:MCXNATURALGAS"], "interval": 1.0}

If no subscribe message is received within 1s, defaults will be used.
"""
import asyncio
import json
import concurrent.futures
from datetime import datetime
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from analytics.live_global import get_live_global_quote
from analytics.live_nse import get_live_nse_quote
from analytics.mcx_live import get_live_mcx_quote

app = FastAPI()

# Thread pool for sync fetchers
EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=6)


def _parse_subscribe_message(text: str) -> dict:
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


async def _fetch_quote(kind: str, symbol: str):
    loop = asyncio.get_event_loop()
    try:
        if kind == "global":
            return await loop.run_in_executor(EXECUTOR, get_live_global_quote, symbol)
        if kind == "nse":
            return await loop.run_in_executor(EXECUTOR, get_live_nse_quote, symbol)
        if kind == "mcx":
            return await loop.run_in_executor(EXECUTOR, get_live_mcx_quote, symbol)
    except Exception:
        return None


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        # Wait briefly for an optional subscription message
        try:
            msg = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
            sub = _parse_subscribe_message(msg)
        except asyncio.TimeoutError:
            sub = {}

        instruments = sub.get("subscribe") or ["global:NG=F", "nse:NIFTY", "mcx:MCXNATURALGAS"]
        interval = float(sub.get("interval", 1.0))

        parsed = []
        for inst in instruments:
            if ":" not in inst:
                continue
            kind, symbol = inst.split(":", 1)
            parsed.append((kind.lower(), symbol))

        if not parsed:
            await websocket.send_text(json.dumps({"error": "no valid subscriptions"}))
            await websocket.close()
            return

        while True:
            tasks = [_fetch_quote(k, s) for k, s in parsed]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            out = {}
            for (k, s), res in zip(parsed, results):
                key = f"{k.upper()}:{s}"
                if isinstance(res, Exception) or res is None:
                    out[key] = {"error": "fetch_failed"}
                else:
                    out[key] = res

            message = {
                "type": "update",
                "timestamp": datetime.utcnow().isoformat(),
                "data": out,
            }

            await websocket.send_text(json.dumps(message, default=str))
            await asyncio.sleep(interval)

    except WebSocketDisconnect:
        return
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass


@app.get("/health")
async def health():
    return {"status": "ok"}
