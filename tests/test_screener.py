import pytest
import pandas as pd
from app.scanner.screener import run_base_screener
from app.indicators.trend import add_trend_indicators
from app.indicators.momentum import add_momentum_indicators
from app.indicators.volume import add_volume_indicators

def test_screener_filters():
    # Construct DF passing all filters
    dates = pd.date_range("2025-01-01", periods=30)
    df = pd.DataFrame({
        "date": dates,
        "open": [1000] * 30,
        "high": [1050] * 30,
        "low": [980] * 30,
        "close": [1020] * 30,
        "volume": [20_000_000] * 30 # Value = 1020 * 20M = 20.4B > 10B
    })
    df = add_trend_indicators(df)
    df = add_momentum_indicators(df)
    df = add_volume_indicators(df)

    # Overwrite RSI to valid range (e.g. 58)
    df['RSI14'] = 58.0
    df['Volume_Ratio'] = 1.6

    passed = run_base_screener(df)
    assert passed is True

    # Fail on price < 200
    df_low_price = df.copy()
    df_low_price['close'] = 150.0
    assert run_base_screener(df_low_price) is False

    # Fail on RSI > 70
    df_overbought = df.copy()
    df_overbought['RSI14'] = 82.0
    assert run_base_screener(df_overbought) is False
