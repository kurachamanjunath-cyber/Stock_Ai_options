import streamlit as st
import threading
import json
import queue
import time

try:
    import websocket
except Exception:
    websocket = None

st.title("WebSocket Live Quotes Client")

if websocket is None:
    st.error("websocket-client not installed. Install via `pip install websocket-client`")
    st.stop()

if "wsq" not in st.session_state:
    st.session_state.wsq = queue.Queue()
    st.session_state.ws_thread = None


def on_message(ws, message):
    try:
        st.session_state.wsq.put(json.loads(message))
    except Exception:
        st.session_state.wsq.put({"raw": message})


def on_open(ws):
    # Subscribe to default instruments
    sub = {"subscribe": ["global:NG=F", "nse:NIFTY", "mcx:MCXNATURALGAS"], "interval": 1.0}
    ws.send(json.dumps(sub))


def run_ws():
    ws = websocket.WebSocketApp("ws://127.0.0.1:8000/ws", on_message=on_message, on_open=on_open)
    ws.run_forever()


if st.button("Start WebSocket Client"):
    if st.session_state.ws_thread is None or not st.session_state.ws_thread.is_alive():
        t = threading.Thread(target=run_ws, daemon=True)
        st.session_state.ws_thread = t
        t.start()

st.markdown("### Latest update")
placeholder = st.empty()

while True:
    try:
        item = st.session_state.wsq.get_nowait()
        placeholder.json(item)
    except Exception:
        time.sleep(0.5)
        st.experimental_rerun()
