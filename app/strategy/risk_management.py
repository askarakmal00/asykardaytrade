import pandas as pd
import numpy as np
from typing import Dict, Any

from app import config

def calculate_trade_levels(
    df: pd.DataFrame, 
    setup_type: str, 
    sr_levels: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Computes Entry Zone (entry_low, entry_high), Stop Loss, TP1, TP2, and Risk/Reward ratio.
    Applies Extended Price Protection and RSI Protection.
    """
    if df.empty:
        return {}

    latest = df.iloc[-1]
    price = float(latest['close'])
    ema9 = float(latest.get('EMA9', price))
    ema21 = float(latest.get('EMA21', price))
    atr = float(latest.get('ATR', price * 0.02)) if not pd.isna(latest.get('ATR')) else price * 0.02

    swing_low = sr_levels.get('swing_low', price * 0.96)
    swing_high = sr_levels.get('swing_high', price * 1.05)
    support_low = sr_levels.get('support_low', price * 0.97)
    resistance_high = sr_levels.get('resistance_high', price * 1.05)

    dist_ema9_pct = float(latest.get('Dist_EMA9_Pct', ((price - ema9) / ema9) * 100.0 if ema9 > 0 else 0))
    rsi = float(latest.get('RSI14', 50.0))

    if setup_type == "PULLBACK":
        # Entry zone is near EMA9 / EMA21 / Support
        entry_low = round(min(price, max(ema21, ema9 * 0.995)), 0)
        entry_high = round(max(price, ema9 * 1.005), 0)
        if entry_low == entry_high:
            entry_low = round(price * 0.995, 0)
            entry_high = round(price * 1.005, 0)
            
        # Stop loss below support low / swing low with buffer or 1.5 ATR
        raw_sl = min(swing_low * 0.99, support_low * 0.99, entry_low - (1.2 * atr))
        stop_loss = round(raw_sl, 0)
        
        risk = max(1.0, entry_high - stop_loss)
        tp1 = round(entry_high + (risk * 1.5), 0)
        tp2 = round(max(resistance_high, entry_high + (risk * 2.0)), 0)

    elif setup_type == "BREAKOUT":
        # Entry zone is around the breakout level / current price
        entry_low = round(price * 0.995, 0)
        entry_high = round(price * 1.005, 0)
        
        # Stop loss below retest level or 1.5 ATR
        raw_sl = min(entry_low * 0.97, entry_low - (1.5 * atr))
        stop_loss = round(raw_sl, 0)
        
        risk = max(1.0, entry_high - stop_loss)
        tp1 = round(entry_high + (risk * 1.5), 0)
        tp2 = round(entry_high + (risk * 2.2), 0)
        
    else: # Default / WATCH
        entry_low = round(price * 0.99, 0)
        entry_high = round(price * 1.01, 0)
        stop_loss = round(price * 0.96, 0)
        risk = max(1.0, entry_high - stop_loss)
        tp1 = round(entry_high + (risk * 1.5), 0)
        tp2 = round(entry_high + (risk * 2.0), 0)

    # Ensure stop loss is strictly below entry low
    if stop_loss >= entry_low:
        stop_loss = round(entry_low * 0.97, 0)

    risk_amount = entry_high - stop_loss
    reward_amount = tp1 - entry_high
    rr_ratio = round(reward_amount / risk_amount, 2) if risk_amount > 0 else 0.0

    entry_zone_str = f"{int(entry_low)} - {int(entry_high)}" if entry_low >= 10 else f"{entry_low:.2f} - {entry_high:.2f}"

    return {
        "price": price,
        "entry_low": entry_low,
        "entry_high": entry_high,
        "entry_zone": entry_zone_str,
        "stop_loss": stop_loss,
        "tp1": tp1,
        "tp2": tp2,
        "risk_reward": rr_ratio,
        "dist_ema9_pct": dist_ema9_pct,
        "rsi": rsi,
        "is_overbought": rsi > 70.0,
        "is_extended": dist_ema9_pct > 3.0,
        "is_severely_extended": dist_ema9_pct > 5.0
    }
