import pytest
import pandas as pd
import numpy as np

from app.indicators.trend import add_trend_indicators
from app.indicators.momentum import add_momentum_indicators
from app.indicators.volume import add_volume_indicators
from app.strategy.support_resistance import find_support_resistance
from app.strategy.pullback import detect_pullback
from app.strategy.breakout import detect_breakout
from app.strategy.risk_management import calculate_trade_levels
from app.strategy.signal_engine import evaluate_signal

@pytest.fixture
def bullish_setup_df():
    # Construct a cleanly trending bullish series
    n = 40
    dates = pd.date_range(start="2025-01-01", periods=n, freq="D")
    prices = [500 + (i * 5) for i in range(n)] # uptrend 500 -> 695
    df = pd.DataFrame({
        "date": dates,
        "open": [p - 2 for p in prices],
        "high": [p + 4 for p in prices],
        "low": [p - 4 for p in prices],
        "close": prices,
        "volume": [2_000_000 + (i * 50_000) for i in range(n)]
    })
    df = add_trend_indicators(df)
    df = add_momentum_indicators(df)
    df = add_volume_indicators(df)
    return df

def test_support_resistance(bullish_setup_df):
    sr = find_support_resistance(bullish_setup_df)
    assert sr["swing_high"] >= sr["swing_low"]
    assert sr["support_low"] <= sr["support_high"]
    assert sr["resistance_low"] <= sr["resistance_high"]

def test_signal_engine_bullish(bullish_setup_df):
    sig = evaluate_signal(bullish_setup_df)
    
    assert "score" in sig
    assert 0 <= sig["score"] <= 100
    assert sig["grade"] in ["A+", "A", "WATCH", "LOW QUALITY", "NO TRADE"]
    assert sig["status"] in ["READY", "WAIT_PULLBACK", "WAIT_BREAKOUT", "WATCH", "NO_TRADE"]
    assert sig["entry_low"] <= sig["entry_high"]
    assert sig["stop_loss"] < sig["entry_low"]
    assert sig["tp1"] > sig["entry_high"]
    assert sig["risk_reward"] > 0
    assert len(sig["why_this_stock"]) > 0

def test_pullback_detection(bullish_setup_df):
    sr = find_support_resistance(bullish_setup_df)
    res = detect_pullback(bullish_setup_df, sr)
    assert "is_pullback" in res
    assert "score_boost" in res

def test_breakout_detection(bullish_setup_df):
    sr = find_support_resistance(bullish_setup_df)
    res = detect_breakout(bullish_setup_df, sr)
    assert "is_breakout" in res
    assert "score_boost" in res
