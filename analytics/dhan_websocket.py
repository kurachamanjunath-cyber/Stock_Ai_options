"""Dhan WebSocket integration for real-time live market data."""
import os
import json
import threading
import time
from typing import Dict, Optional, Callable, List
from datetime import datetime
import pandas as pd
import queue

class DhanWebSocketClient:
    """
    Dhan WebSocket client for real-time price updates.
    
    Connects to Dhan's WebSocket feed for live MCX, NSE, and global futures data.
    
    Usage:
        client = DhanWebSocketClient(api_key, client_id)
        client.subscribe_to_symbol("NIFTY")
        price = client.get_latest_price("NIFTY")
    """
    
    def __init__(self, api_key: Optional[str] = None, client_id: Optional[str] = None):
        """
        Initialize WebSocket client.
        
        Args:
            api_key: Dhan API key (or set DHAN_API_KEY env var)
            client_id: Dhan client ID (or set DHAN_CLIENT_ID env var)
        """
        self.api_key = api_key or os.getenv("DHAN_API_KEY")
        self.client_id = client_id or os.getenv("DHAN_CLIENT_ID")
        self.ws = None
        self.is_connected = False
        self.price_data = {}  # {symbol: {price, bid, ask, volume, timestamp}}
        self.subscribed_symbols = set()
        self.data_queue = queue.Queue()
        self.callbacks = {}  # {symbol: [callback_functions]}
        self.lock = threading.Lock()
        
        # WebSocket URL for Dhan
        self.ws_url = "wss://api-feed.dhan.co"
        
    def connect(self) -> bool:
        """
        Connect to Dhan WebSocket.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            import websocket
            
            if not self.api_key or not self.client_id:
                print("❌ Dhan API credentials not found. Set DHAN_API_KEY and DHAN_CLIENT_ID")
                return False
            
            # Start WebSocket connection in background thread
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open
            )
            
            # Connect in background thread
            ws_thread = threading.Thread(target=self._run_ws, daemon=True)
            ws_thread.start()
            
            # Wait for connection
            time.sleep(2)
            
            if self.is_connected:
                print("✅ Dhan WebSocket connected")
                return True
            else:
                print("❌ Failed to establish WebSocket connection")
                return False
        
        except ImportError:
            print("❌ websocket-client not installed. Run: pip install websocket-client")
            return False
        except Exception as e:
            print(f"❌ WebSocket connection error: {e}")
            return False
    
    def _run_ws(self):
        """Run WebSocket connection in background."""
        try:
            self.ws.run_forever()
        except Exception as e:
            print(f"WebSocket error: {e}")
            self.is_connected = False
    
    def _on_open(self, ws):
        """Called when WebSocket connects."""
        self.is_connected = True
        # Authenticate
        auth_msg = {
            "type": "AUTH",
            "apiKey": self.api_key,
            "clientId": self.client_id
        }
        ws.send(json.dumps(auth_msg))
    
    def _on_message(self, ws, message):
        """Called when WebSocket receives a message."""
        try:
            data = json.loads(message)
            
            if data.get("type") == "PRICE_UPDATE":
                symbol = data.get("symbol")
                
                with self.lock:
                    self.price_data[symbol] = {
                        "price": data.get("ltp"),
                        "bid": data.get("bid"),
                        "ask": data.get("ask"),
                        "volume": data.get("volume"),
                        "open_interest": data.get("oi"),
                        "timestamp": datetime.now(),
                        "high": data.get("high"),
                        "low": data.get("low"),
                        "open": data.get("open"),
                        "close": data.get("close"),
                        "volume_total": data.get("volume_total")
                    }
                
                # Execute callbacks
                if symbol in self.callbacks:
                    for callback in self.callbacks[symbol]:
                        try:
                            callback(self.price_data[symbol])
                        except Exception as e:
                            print(f"Callback error: {e}")
                
                # Put in queue for Streamlit
                self.data_queue.put((symbol, self.price_data[symbol]))
        
        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"Message processing error: {e}")
    
    def _on_error(self, ws, error):
        """Called on WebSocket error."""
        print(f"❌ WebSocket error: {error}")
        self.is_connected = False
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Called when WebSocket closes."""
        self.is_connected = False
        print(f"WebSocket closed: {close_msg}")
    
    def subscribe(self, symbol: str, callback: Optional[Callable] = None) -> bool:
        """
        Subscribe to a symbol for real-time updates.
        
        Args:
            symbol: Symbol name (NIFTY, SENSEX, MCXGOLD, etc.)
            callback: Optional callback function to call on price updates
        
        Returns:
            True if subscribed successfully
        """
        try:
            if not self.is_connected:
                return False
            
            with self.lock:
                self.subscribed_symbols.add(symbol)
                
                if callback:
                    if symbol not in self.callbacks:
                        self.callbacks[symbol] = []
                    self.callbacks[symbol].append(callback)
            
            # Send subscription message
            sub_msg = {
                "type": "SUBSCRIBE",
                "symbols": [symbol]
            }
            self.ws.send(json.dumps(sub_msg))
            return True
        
        except Exception as e:
            print(f"Subscription error: {e}")
            return False
    
    def unsubscribe(self, symbol: str) -> bool:
        """
        Unsubscribe from a symbol.
        
        Args:
            symbol: Symbol name
        
        Returns:
            True if unsubscribed successfully
        """
        try:
            if not self.is_connected:
                return False
            
            with self.lock:
                if symbol in self.subscribed_symbols:
                    self.subscribed_symbols.remove(symbol)
                if symbol in self.callbacks:
                    del self.callbacks[symbol]
            
            # Send unsubscription message
            unsub_msg = {
                "type": "UNSUBSCRIBE",
                "symbols": [symbol]
            }
            self.ws.send(json.dumps(unsub_msg))
            return True
        
        except Exception as e:
            print(f"Unsubscription error: {e}")
            return False
    
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """
        Get latest price for a symbol.
        
        Args:
            symbol: Symbol name
        
        Returns:
            Latest price or None if not available
        """
        with self.lock:
            if symbol in self.price_data:
                return self.price_data[symbol].get("price")
        return None
    
    def get_ohlcv(self, symbol: str) -> Optional[Dict]:
        """
        Get OHLCV data for a symbol.
        
        Args:
            symbol: Symbol name
        
        Returns:
            Dict with OHLCV or None if not available
        """
        with self.lock:
            if symbol in self.price_data:
                data = self.price_data[symbol]
                return {
                    "open": data.get("open"),
                    "high": data.get("high"),
                    "low": data.get("low"),
                    "close": data.get("close"),
                    "volume": data.get("volume")
                }
        return None
    
    def get_all_data(self, symbol: str) -> Optional[Dict]:
        """
        Get all available data for a symbol.
        
        Args:
            symbol: Symbol name
        
        Returns:
            Full data dict or None
        """
        with self.lock:
            if symbol in self.price_data:
                return self.price_data[symbol].copy()
        return None
    
    def disconnect(self):
        """Disconnect from WebSocket."""
        try:
            with self.lock:
                self.subscribed_symbols.clear()
                self.callbacks.clear()
            
            if self.ws:
                self.ws.close()
            self.is_connected = False
            print("✅ WebSocket disconnected")
        except Exception as e:
            print(f"Disconnect error: {e}")


# Global WebSocket client instance for Streamlit
_ws_client = None

def get_dhan_websocket() -> Optional[DhanWebSocketClient]:
    """Get or create global WebSocket client."""
    global _ws_client
    
    if _ws_client is None:
        _ws_client = DhanWebSocketClient()
        if not _ws_client.connect():
            _ws_client = None
    
    return _ws_client


def subscribe_to_live_data(symbol: str) -> bool:
    """
    Subscribe to live data for a symbol.
    
    Args:
        symbol: Symbol name
    
    Returns:
        True if subscribed
    """
    client = get_dhan_websocket()
    if client:
        return client.subscribe(symbol)
    return False


def get_live_price(symbol: str) -> Optional[float]:
    """
    Get live price from WebSocket.
    
    Args:
        symbol: Symbol name
    
    Returns:
        Price or None
    """
    client = get_dhan_websocket()
    if client:
        return client.get_latest_price(symbol)
    return None


def get_live_ohlcv(symbol: str) -> Optional[Dict]:
    """
    Get live OHLCV from WebSocket.
    
    Args:
        symbol: Symbol name
    
    Returns:
        OHLCV dict or None
    """
    client = get_dhan_websocket()
    if client:
        return client.get_ohlcv(symbol)
    return None
