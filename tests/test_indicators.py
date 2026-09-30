import pytest
import pandas as pd
import numpy as np

from app.indicators.trend import add_trend_indicators
from app.indicators.momentum import add_momentum_indicators
from app.indicators.volume import add_volume_indicators

@pytest.fixture
def sample_ohlcv():
    np.random.seed(42)
    n = 60
    base_price = 1000.0
    returns = np.random.normal(0.001, 0.02, n)
    prices = base_price * np.cumprod(1 + returns)
    
    dates = pd.date_range(start="2025-01-01", periods=n, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "open": prices * (1 - 0.005),
        "high": prices * (1 + 0.015),
        "low": prices * (1 - 0.015),
        "close": prices,
        "volume": np.random.randint(1_000_000, 5_000_000, n)
    })
    return df

def test_trend_indicators(sample_ohlcv):
    df = add_trend_indicators(sample_ohlcv.copy())
    
    assert "EMA9" in df.columns
    assert "EMA21" in df.columns
    assert "MA20" in df.columns
    assert "MA50" in df.columns
    assert "Dist_EMA9_Pct" in df.columns
    assert "ATR" in df.columns
    
    # Check latest values are reasonable
    latest = df.iloc[-1]
    assert not pd.isna(latest["EMA9"])
    assert not pd.isna(latest["EMA21"])
    assert latest["EMA9"] > 0
    assert latest["EMA21"] > 0

def test_momentum_indicators(sample_ohlcv):
    df = add_momentum_indicators(sample_ohlcv.copy())
    
    assert "RSI14" in df.columns
    assert "Stoch_RSI" in df.columns
    
    latest = df.iloc[-1]
    assert 0 <= latest["RSI14"] <= 100
    assert 0 <= latest["Stoch_RSI"] <= 100

def test_volume_indicators(sample_ohlcv):
    df = add_volume_indicators(sample_ohlcv.copy())
    
    assert "Volume_MA20" in df.columns
    assert "Volume_Ratio" in df.columns
    assert "Estimated_Value" in df.columns
    
    latest = df.iloc[-1]
    assert latest["Volume_MA20"] > 0
    assert latest["Volume_Ratio"] > 0
    assert latest["Estimated_Value"] == latest["close"] * latest["volume"]
