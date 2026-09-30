import pandas as pd
from app import config

def run_base_screener(df: pd.DataFrame) -> bool:
    """
    Runs the base screener on the latest row of a dataframe.
    Filters:
    - Price > MIN_PRICE (default 200)
    - RSI_MIN <= RSI14 <= RSI_MAX (default 50 - 70)
    - Volume >= MIN_VOLUME (default 1,000,000)
    - Estimated_Value >= MIN_VALUE (default 10,000,000,000)
    - Volume_Ratio >= MIN_VOLUME_RATIO (default 1.5) or Volume >= Volume_MA20
    """
    if df.empty or len(df) < 5:
        return False
        
    latest = df.iloc[-1]

    # Required columns check
    required_cols = ['close', 'RSI14', 'volume', 'Estimated_Value', 'Volume_Ratio']
    for col in required_cols:
        if col not in latest or pd.isna(latest[col]):
            return False

    # Price Filter
    if latest['close'] < config.MIN_PRICE:
        return False

    # RSI Filter (50 to 70 preferred)
    if latest['RSI14'] < config.RSI_MIN or latest['RSI14'] > config.RSI_MAX:
        return False

    # Volume & Value Filter
    if latest['volume'] < config.MIN_VOLUME:
        return False
        
    if latest['Estimated_Value'] < config.MIN_VALUE:
        return False

    # Volume Momentum
    if latest['Volume_Ratio'] < 1.0:
        return False

    return True
