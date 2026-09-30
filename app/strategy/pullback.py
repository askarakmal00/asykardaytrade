import pandas as pd
from typing import Dict, Any

def detect_pullback(df: pd.DataFrame, sr_levels: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detects if the current candle pattern matches a valid Pullback setup.
    """
    if df.empty or len(df) < 5:
        return {"is_pullback": False, "score_boost": 0, "status": "NONE", "reasons": []}

    latest = df.iloc[-1]
    price = float(latest['close'])
    ema9 = float(latest.get('EMA9', price))
    ema21 = float(latest.get('EMA21', price))
    rsi = float(latest.get('RSI14', 50.0))
    vol_ratio = float(latest.get('Volume_Ratio', 1.0))
    dist_ema9_pct = float(latest.get('Dist_EMA9_Pct', 0.0))

    trend_bullish = (price >= ema9 * 0.985) and (ema9 >= ema21 * 0.99)
    support_valid = price >= float(sr_levels.get('support_low', 0)) * 0.99
    near_ema_pullback = abs(dist_ema9_pct) <= 2.5 or (price <= ema9 * 1.01 and price >= ema21 * 0.98)
    momentum_recovering = (rsi >= 45.0) and (rsi <= 68.0)

    is_pullback = trend_bullish and support_valid and (near_ema_pullback or dist_ema9_pct <= 3.0)

    score_boost = 0
    reasons = []
    if is_pullback:
        score_boost += 15 # Base pullback setup
        reasons.append("Valid pullback toward dynamic support (EMA9/EMA21)")
        
        if support_valid:
            score_boost += 5
            reasons.append("Support zone remains structurally valid")
            
        if momentum_recovering:
            score_boost += 5
            reasons.append("Momentum recovering without overbought exhaustion")

    # Determine status
    if is_pullback:
        if dist_ema9_pct > 3.0:
            status = "WAIT_PULLBACK"
        elif momentum_recovering and near_ema_pullback:
            status = "READY"
        else:
            status = "WAIT_PULLBACK"
    else:
        status = "NONE"

    return {
        "is_pullback": is_pullback,
        "score_boost": score_boost,
        "status": status,
        "reasons": reasons
    }
