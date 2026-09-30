import pandas as pd
from ta.momentum import RSIIndicator, StochRSIIndicator

def add_momentum_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds RSI14 and Stochastic RSI to the DataFrame.
    Expects a DataFrame with a 'close' column.
    """
    if df.empty or 'close' not in df.columns or len(df) < 5:
        return df

    # RSI14
    window_rsi = min(14, len(df) - 1)
    if window_rsi >= 2:
        try:
            df['RSI14'] = RSIIndicator(close=df['close'], window=window_rsi).rsi()
        except Exception:
            df['RSI14'] = 50.0
    else:
        df['RSI14'] = 50.0
    
    # Stochastic RSI
    try:
        stoch_rsi = StochRSIIndicator(close=df['close'], window=window_rsi, smooth1=3, smooth2=3)
        df['Stoch_RSI'] = stoch_rsi.stochrsi() * 100.0  # 0-100 scale
        df['Stoch_RSI_K'] = stoch_rsi.stochrsi_k() * 100.0
        df['Stoch_RSI_D'] = stoch_rsi.stochrsi_d() * 100.0
    except Exception:
        df['Stoch_RSI'] = 50.0
        df['Stoch_RSI_K'] = 50.0
        df['Stoch_RSI_D'] = 50.0

    return df
