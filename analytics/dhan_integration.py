"""Dhan API integration for live MCX, NIFTY, SENSEX options data."""
import os
import requests
from typing import Dict, Optional, List
import pandas as pd
from datetime import datetime, timedelta

class DhanAPIClient:
    """
    Dhan API client for fetching live options data and prices.
    
    NOTE: This is a template for Dhan API integration.
    To use this, you'll need:
    1. Dhan API account and credentials
    2. Install dhan package: pip install dhan
    3. Set environment variables: DHAN_API_KEY and DHAN_CLIENT_ID
    """
    
    def __init__(self, api_key: Optional[str] = None, client_id: Optional[str] = None):
        """
        Initialize Dhan API client.
        
        Args:
            api_key: Dhan API key (or set DHAN_API_KEY env var)
            client_id: Dhan client ID (or set DHAN_CLIENT_ID env var)
        """
        self.api_key = api_key or os.getenv("DHAN_API_KEY")
        self.client_id = client_id or os.getenv("DHAN_CLIENT_ID")
        self.base_url = "https://api.dhan.co"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.is_connected = self.test_connection()
    
    def test_connection(self) -> bool:
        """Test if API connection is working."""
        if not self.api_key or not self.client_id:
            return False
        try:
            # Try a simple API call
            response = requests.get(
                f"{self.base_url}/user/profile",
                headers=self.headers,
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Dhan API connection failed: {e}")
            return False
    
    def get_live_price(self, security_id: str) -> Optional[Dict]:
        """
        Get live price for a security.
        
        Args:
            security_id: Dhan security ID
        
        Returns:
            Dict with price data or None if failed
        """
        if not self.is_connected:
            return None
        
        try:
            response = requests.get(
                f"{self.base_url}/quotes/{security_id}",
                headers=self.headers,
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error fetching live price: {e}")
            return None
    
    def get_option_chain(self, symbol: str, expiry_date: str) -> Optional[List[Dict]]:
        """
        Get option chain for a symbol and expiry.
        
        Args:
            symbol: Symbol name (e.g., "NIFTY", "MCXGOLD")
            expiry_date: Expiry date in YYYY-MM-DD format
        
        Returns:
            List of option chain data or None if failed
        """
        if not self.is_connected:
            return None
        
        try:
            response = requests.get(
                f"{self.base_url}/options/chain",
                headers=self.headers,
                params={
                    "symbol": symbol,
                    "expiry": expiry_date
                },
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error fetching option chain: {e}")
            return None
    
    def get_nifty_option_data(self, expiry_date: str = None) -> Optional[pd.DataFrame]:
        """
        Get NIFTY option chain data.
        
        Args:
            expiry_date: Expiry date (defaults to next Thursday)
        
        Returns:
            DataFrame with option chain or None if failed
        """
        if expiry_date is None:
            # Get next Thursday
            today = datetime.now()
            days_until_thursday = (3 - today.weekday()) % 7
            if days_until_thursday == 0 and today.hour < 15:
                days_until_thursday = 0
            else:
                days_until_thursday = (3 - today.weekday()) % 7 or 7
            expiry_date = (today + timedelta(days=days_until_thursday)).strftime("%Y-%m-%d")
        
        chain = self.get_option_chain("NIFTY", expiry_date)
        if chain:
            return pd.DataFrame(chain)
        return None
    
    def get_sensex_option_data(self, expiry_date: str = None) -> Optional[pd.DataFrame]:
        """
        Get SENSEX option chain data.
        
        Args:
            expiry_date: Expiry date (defaults to next Thursday)
        
        Returns:
            DataFrame with option chain or None if failed
        """
        if expiry_date is None:
            today = datetime.now()
            days_until_thursday = (3 - today.weekday()) % 7
            if days_until_thursday == 0 and today.hour < 15:
                days_until_thursday = 0
            else:
                days_until_thursday = (3 - today.weekday()) % 7 or 7
            expiry_date = (today + timedelta(days=days_until_thursday)).strftime("%Y-%m-%d")
        
        chain = self.get_option_chain("SENSEX", expiry_date)
        if chain:
            return pd.DataFrame(chain)
        return None
    
    def get_mcx_option_data(self, commodity: str, expiry_date: str = None) -> Optional[pd.DataFrame]:
        """
        Get MCX commodity option chain data.
        
        Args:
            commodity: Commodity name (e.g., "GOLD", "SILVER", "CRUDE")
            expiry_date: Expiry date
        
        Returns:
            DataFrame with option chain or None if failed
        """
        if expiry_date is None:
            # MCX options typically expire on 5th of next month
            today = datetime.now()
            if today.day < 5:
                next_month = today
            else:
                if today.month == 12:
                    next_month = today.replace(year=today.year + 1, month=1, day=1)
                else:
                    next_month = today.replace(month=today.month + 1, day=1)
            expiry_date = f"{next_month.year}-{next_month.month:02d}-05"
        
        chain = self.get_option_chain(f"MCX{commodity}", expiry_date)
        if chain:
            return pd.DataFrame(chain)
        return None
    
    def find_atm_call_put(self, current_price: float, chain_df: pd.DataFrame) -> Dict:
        """
        Find ATM call and put options from option chain.
        
        Args:
            current_price: Current market price
            chain_df: Option chain DataFrame
        
        Returns:
            Dict with ATM call and put data
        """
        if chain_df is None or chain_df.empty:
            return {"error": "No option chain data"}
        
        # Find strike closest to current price
        if 'strike' in chain_df.columns:
            chain_df['distance'] = abs(chain_df['strike'] - current_price)
            atm_strike = chain_df.loc[chain_df['distance'].idxmin()]
            
            call_data = chain_df[chain_df['strike'] == atm_strike['strike']]
            put_data = chain_df[chain_df['strike'] == atm_strike['strike']]
            
            # Filter for call and put
            if 'type' in call_data.columns:
                call = call_data[call_data['type'] == 'CE'].iloc[0] if len(call_data[call_data['type'] == 'CE']) > 0 else None
                put = put_data[put_data['type'] == 'PE'].iloc[0] if len(put_data[put_data['type'] == 'PE']) > 0 else None
            else:
                call = call_data.iloc[0] if len(call_data) > 0 else None
                put = put_data.iloc[0] if len(put_data) > 0 else None
            
            return {
                "atm_strike": float(atm_strike['strike']),
                "call": call.to_dict() if call is not None else None,
                "put": put.to_dict() if put is not None else None,
                "current_price": current_price
            }
        
        return {"error": "Invalid option chain format"}


def get_option_premium_from_dhan(
    symbol: str,
    current_price: float,
    strike: float,
    option_type: str = "CE",
    expiry: str = None
) -> Optional[float]:
    """
    Get option premium from Dhan API.
    
    Args:
        symbol: Symbol name (NIFTY, SENSEX, MCXGOLD, etc.)
        current_price: Current market price
        strike: Strike price
        option_type: "CE" for call, "PE" for put
        expiry: Expiry date
    
    Returns:
        Premium price or None if not available
    """
    try:
        client = DhanAPIClient()
        
        if not client.is_connected:
            return None
        
        # Fetch option chain
        if symbol == "NIFTY":
            chain = client.get_nifty_option_data(expiry)
        elif symbol == "SENSEX":
            chain = client.get_sensex_option_data(expiry)
        elif symbol.startswith("MCX"):
            commodity = symbol.replace("MCX", "")
            chain = client.get_mcx_option_data(commodity, expiry)
        else:
            return None
        
        if chain is None or chain.empty:
            return None
        
        # Find matching option
        mask = (chain['strike'] == strike) & (chain['type'] == option_type)
        if len(chain[mask]) > 0:
            return float(chain[mask].iloc[0]['lastPrice'])
        
        return None
    
    except Exception as e:
        print(f"Error getting option premium: {e}")
        return None
