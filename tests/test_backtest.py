import pytest
from app.backtest.metrics import calculate_backtest_metrics

def test_backtest_metrics_calculation():
    sample_trades = [
        {
            "symbol": "BBCA.JK",
            "setup": "PULLBACK",
            "entry_date": "2025-01-10",
            "exit_date": "2025-01-12",
            "entry_price": 1000.0,
            "exit_price": 1050.0,
            "pnl_amount": 500000.0,
            "pnl_pct": 5.0,
            "r_multiple": 2.0,
            "result": "WIN"
        },
        {
            "symbol": "BRMS.JK",
            "setup": "BREAKOUT",
            "entry_date": "2025-01-15",
            "exit_date": "2025-01-17",
            "entry_price": 600.0,
            "exit_price": 580.0,
            "pnl_amount": -200000.0,
            "pnl_pct": -3.3,
            "r_multiple": -1.0,
            "result": "LOSS"
        },
        {
            "symbol": "HRUM.JK",
            "setup": "PULLBACK",
            "entry_date": "2025-01-20",
            "exit_date": "2025-01-22",
            "entry_price": 800.0,
            "exit_price": 860.0,
            "pnl_amount": 600000.0,
            "pnl_pct": 7.5,
            "r_multiple": 2.5,
            "result": "WIN"
        }
    ]

    metrics = calculate_backtest_metrics(sample_trades)
    
    assert metrics["total_trades"] == 3
    assert metrics["wins"] == 2
    assert metrics["losses"] == 1
    assert round(metrics["win_rate"], 1) == 66.7
    assert metrics["profit_factor"] == 5.5  # (500k + 600k) / 200k = 1.1M / 200k = 5.5
    assert metrics["avg_r"] > 0
    assert "pullback_metrics" in metrics
    assert "breakout_metrics" in metrics
    assert len(metrics["equity_curve"]) == 4 # Initial + 3 trades
