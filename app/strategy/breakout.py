import pandas as pd
from typing import Dict, Any

def detect_breakout(df: pd.DataFrame, sr_levels: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detects if the current candle pattern matches a valid Breakout setup.
    """
    if df.empty or len(df) < 5:
        return {"is_breakout": False, "score_boost": 0, "status": "NONE", "reasons": []}

    latest = df.iloc[-1]
    price = float(latest['close'])
    high = float(latest['high'])
    ema9 = float(latest.get('EMA9', price))
    vol_ratio = float(latest.get('Volume_Ratio', 1.0))
    rsi = float(latest.get('RSI14', 50.0))
    dist_ema9_pct = float(latest.get('Dist_EMA9_Pct', 0.0))

    prev_high = float(sr_levels.get('prev_high', price))
    resistance_low = float(sr_levels.get('resistance_low', price * 1.02))

    # Consolidation check: recent candle range is within 5-7%
    recent_high = df['high'].tail(5).max()
    recent_low = df['low'].tail(5).min()
    consolidation = (recent_high - recent_low) / max(1.0, recent_low) <= 0.08

    near_resistance = (price >= resistance_low * 0.98) or (high >= prev_high * 0.995)
    volume_surge = vol_ratio >= 1.4

    is_breakout = near_resistance and (volume_surge or consolidation) and (price >= ema9)

    score_boost = 0
    reasons = []
    if is_breakout:
        score_boost += 15 # Base breakout setup
        reasons.append("Valid consolidation / breakout structure near key resistance")
        
        if volume_surge:
            score_boost += 5
            reasons.append("Volume expansion confirmed (> 1.4x 20-day average)")
            
        if consolidation:
            score_boost += 5
            reasons.append("Controlled consolidation range prior to expansion")

    if is_breakout:
        if price >= prev_high and volume_surge and dist_ema9_pct <= 4.0:
            status = "READY"
        else:
            status = "WAIT_BREAKOUT"
    else:
        status = "NONE"

    return {
        "is_breakout": is_breakout,
        "score_boost": score_boost,
        "status": status,
        "reasons": reasons
    }
