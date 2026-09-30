import pandas as pd
from ta.trend import SMAIndicator

def add_volume_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds Volume MA20, Volume Ratio, Volume Change %, and Estimated Value.
    Expects DataFrame with 'close' and 'volume' columns.
    """
    if df.empty or 'close' not in df.columns or 'volume' not in df.columns or len(df) < 2:
        return df

    # Volume MA20
    window_vol = min(20, len(df))
    df['Volume_MA20'] = SMAIndicator(close=df['volume'], window=window_vol).sma_indicator()
    
    # Fill any 0 or NA in Volume_MA20 to avoid division by zero
    safe_ma = df['Volume_MA20'].replace(0, 1).fillna(df['volume'])
    
    # Volume Ratio
    df['Volume_Ratio'] = df['volume'] / safe_ma
    
    # Volume Change %
    df['Volume_Change_Pct'] = df['volume'].pct_change() * 100.0
    
    # Estimated Value (Close * Volume in IDR)
    df['Estimated_Value'] = df['close'] * df['volume']

    return df
