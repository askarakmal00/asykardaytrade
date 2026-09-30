import pandas as pd
import numpy as np
from ta.trend import EMAIndicator, SMAIndicator
from ta.volatility import AverageTrueRange

def add_trend_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds EMA9, EMA21, MA20, MA50, EMA21 Slope, Distance from EMA9 %, and ATR.
    Expects DataFrame with 'close', 'high', 'low' columns.
    """
    if df.empty or 'close' not in df.columns or len(df) < 5:
        return df

    # EMA
    df['EMA9'] = EMAIndicator(close=df['close'], window=min(9, len(df))).ema_indicator()
    df['EMA21'] = EMAIndicator(close=df['close'], window=min(21, len(df))).ema_indicator()
    
    # SMA (MA)
    df['MA20'] = SMAIndicator(close=df['close'], window=min(20, len(df))).sma_indicator()
    df['MA50'] = SMAIndicator(close=df['close'], window=min(50, len(df))).sma_indicator()

    # EMA21 Slope (3-period difference or percentage change)
    if 'EMA21' in df.columns:
        df['EMA21_Slope'] = df['EMA21'].diff(periods=3)

    # Distance From EMA9 %: ((Price - EMA9) / EMA9) * 100
    if 'EMA9' in df.columns:
        df['Dist_EMA9_Pct'] = ((df['close'] - df['EMA9']) / df['EMA9']) * 100.0

    # ATR for volatility and Stop Loss estimation
    if 'high' in df.columns and 'low' in df.columns:
        try:
            atr = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=min(14, len(df)))
            df['ATR'] = atr.average_true_range()
        except Exception:
            df['ATR'] = df['close'] * 0.02

    return df
