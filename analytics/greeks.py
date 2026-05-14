"""Black-Scholes Greeks calculator for options valuation."""
import numpy as np
from scipy.stats import norm
from typing import Dict, Tuple

def calculate_greeks(
    S: float,
    K: float,
    T: float,
    r: float = 0.05,
    sigma: float = 0.2,
    option_type: str = 'call'
) -> Dict[str, float]:
    """
    Calculate Black-Scholes Greeks for European options.
    
    Args:
        S: Current stock price
        K: Strike price
        T: Time to expiration in years (e.g., 30 days = 30/365)
        r: Risk-free rate (default 5%)
        sigma: Volatility/standard deviation (default 20%)
        option_type: 'call' or 'put'
    
    Returns:
        Dict with delta, gamma, theta, vega, rho, and premium
    """
    
    if T <= 0 or sigma <= 0 or K <= 0 or S <= 0:
        return {
            "delta": 0.0,
            "gamma": 0.0,
            "theta": 0.0,
            "vega": 0.0,
            "rho": 0.0,
            "premium": 0.0,
            "error": "Invalid input parameters"
        }
    
    try:
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        N_d1 = norm.cdf(d1)
        n_d1 = norm.pdf(d1)
        N_d2 = norm.cdf(d2)
        N_minus_d2 = norm.cdf(-d2)
        
        if option_type.lower() == 'call':
            # Call Greeks
            delta = N_d1
            premium = S * N_d1 - K * np.exp(-r * T) * N_d2
            theta = (-S * n_d1 * sigma / (2 * np.sqrt(T)) - 
                    r * K * np.exp(-r * T) * N_d2) / 365
            rho = K * T * np.exp(-r * T) * N_d2 / 100
        else:  # put
            # Put Greeks
            delta = N_d1 - 1
            premium = K * np.exp(-r * T) * N_minus_d2 - S * (1 - N_d1)
            theta = (-S * n_d1 * sigma / (2 * np.sqrt(T)) + 
                    r * K * np.exp(-r * T) * (1 - N_d2)) / 365
            rho = -K * T * np.exp(-r * T) * N_minus_d2 / 100
        
        # Gamma and Vega are same for calls and puts
        gamma = n_d1 / (S * sigma * np.sqrt(T))
        vega = S * n_d1 * np.sqrt(T) / 100
        
        return {
            "delta": float(delta),
            "gamma": float(gamma),
            "theta": float(theta),
            "vega": float(vega),
            "rho": float(rho),
            "premium": float(premium)
        }
    
    except Exception as e:
        return {
            "delta": 0.0,
            "gamma": 0.0,
            "theta": 0.0,
            "vega": 0.0,
            "rho": 0.0,
            "premium": 0.0,
            "error": str(e)
        }


def estimate_atm_strike(current_price: float, strike_interval: float = None) -> float:
    """
    Estimate ATM (At-The-Money) strike for current price.
    
    Args:
        current_price: Current market price
        strike_interval: Strike interval (e.g., 100 for GOLD, 50 for indices)
    
    Returns:
        Nearest ATM strike price
    """
    if strike_interval is None:
        strike_interval = round(current_price / 10) * 5 or 100
    
    return round(current_price / strike_interval) * strike_interval


def calculate_option_premium_percentage(premium: float, current_price: float) -> float:
    """Calculate option premium as percentage of underlying price."""
    if current_price <= 0:
        return 0.0
    return (premium / current_price) * 100


def calculate_breakeven_points(
    entry_premium: float,
    strike_price: float,
    option_type: str = 'call'
) -> Dict[str, float]:
    """
    Calculate breakeven points for an option trade.
    
    Args:
        entry_premium: Price paid for the option
        strike_price: Strike price of the option
        option_type: 'call' or 'put'
    
    Returns:
        Dict with breakeven price and margins
    """
    if option_type.lower() == 'call':
        breakeven = strike_price + entry_premium
    else:  # put
        breakeven = strike_price - entry_premium
    
    return {
        "breakeven": float(breakeven),
        "profit_margin": float(entry_premium),
        "loss_margin": float(entry_premium)
    }
