import pandas as pd
import numpy as np
from typing import Dict, Any

def find_support_resistance(df: pd.DataFrame, window: int = 10) -> Dict[str, Any]:
    """
    Computes Support and Resistance levels and zones based on recent swing highs/lows,
    moving averages, and historical highs/lows.
    """
    if df.empty or len(df) < 5:
        close = df['close'].iloc[-1] if not df.empty else 0.0
        return {
            "swing_high": close * 1.05,
            "swing_low": close * 0.95,
            "support_low": close * 0.95,
            "support_high": close * 0.98,
            "resistance_low": close * 1.02,
            "resistance_high": close * 1.05,
            "support_zone": f"{int(close * 0.95)} - {int(close * 0.98)}",
            "resistance_zone": f"{int(close * 1.02)} - {int(close * 1.05)}",
        }

    recent = df.tail(window)
    swing_high = float(recent['high'].max())
    swing_low = float(recent['low'].min())
    
    prev_high = float(df['high'].iloc[-2]) if len(df) >= 2 else swing_high
    prev_low = float(df['low'].iloc[-2]) if len(df) >= 2 else swing_low
    
    latest_close = float(df['close'].iloc[-1])
    ema9 = float(df['EMA9'].iloc[-1]) if 'EMA9' in df and not pd.isna(df['EMA9'].iloc[-1]) else latest_close
    ema21 = float(df['EMA21'].iloc[-1]) if 'EMA21' in df and not pd.isna(df['EMA21'].iloc[-1]) else latest_close

    # Support zone: cluster near swing low / EMA21 / EMA9 lower bound
    candidates_support = [swing_low, ema21, prev_low]
    support_val = min(c for c in candidates_support if c <= latest_close + 1e-5) if any(c <= latest_close + 1e-5 for c in candidates_support) else latest_close * 0.97
    support_low = round(support_val * 0.99, 1)
    support_high = round(support_val * 1.005, 1)

    # Resistance zone: cluster near swing high / prev high
    candidates_resistance = [swing_high, prev_high]
    resistance_val = max(c for c in candidates_resistance if c >= latest_close - 1e-5) if any(c >= latest_close - 1e-5 for c in candidates_resistance) else latest_close * 1.03
    resistance_low = round(resistance_val * 0.995, 1)
    resistance_high = round(resistance_val * 1.01, 1)

    # Format zones
    support_zone = f"{int(support_low)} - {int(support_high)}" if support_low >= 10 else f"{support_low:.2f} - {support_high:.2f}"
    resistance_zone = f"{int(resistance_low)} - {int(resistance_high)}" if resistance_low >= 10 else f"{resistance_low:.2f} - {resistance_high:.2f}"

    return {
        "swing_high": swing_high,
        "swing_low": swing_low,
        "prev_high": prev_high,
        "prev_low": prev_low,
        "support_low": support_low,
        "support_high": support_high,
        "resistance_low": resistance_low,
        "resistance_high": resistance_high,
        "support_zone": support_zone,
        "resistance_zone": resistance_zone
    }
