import math
from typing import List, Dict, Any

def calculate_backtest_metrics(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Computes summary backtest performance metrics and setup comparisons.
    """
    if not trades:
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "avg_r": 0.0,
            "max_drawdown": 0.0,
            "pullback_metrics": {"trades": 0, "win_rate": 0.0, "profit_factor": 0.0, "avg_r": 0.0},
            "breakout_metrics": {"trades": 0, "win_rate": 0.0, "profit_factor": 0.0, "avg_r": 0.0},
            "equity_curve": []
        }

    total_trades = len(trades)
    wins = [t for t in trades if t["result"] == "WIN"]
    losses = [t for t in trades if t["result"] == "LOSS"]

    win_count = len(wins)
    loss_count = len(losses)
    win_rate = round((win_count / total_trades) * 100.0, 1) if total_trades > 0 else 0.0

    gross_profit = sum(t["pnl_amount"] for t in wins)
    gross_loss = sum(abs(t["pnl_amount"]) for t in losses)

    avg_win = round(gross_profit / win_count, 2) if win_count > 0 else 0.0
    avg_loss = round(gross_loss / loss_count, 2) if loss_count > 0 else 0.0

    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

    avg_r = round(sum(t.get("r_multiple", 0.0) for t in trades) / total_trades, 2) if total_trades > 0 else 0.0
    
    # Expectancy in R: (Win Rate * Avg R Win) - (Loss Rate * 1.0)
    win_pct = win_count / total_trades if total_trades > 0 else 0.0
    loss_pct = loss_count / total_trades if total_trades > 0 else 0.0
    avg_win_r = sum(t.get("r_multiple", 0.0) for t in wins) / win_count if win_count > 0 else 0.0
    expectancy = round((win_pct * avg_win_r) - (loss_pct * 1.0), 2)

    # Equity Curve & Max Drawdown
    equity = 100_000_000.0 # Starting capital 100M IDR for simulation
    peak = equity
    max_dd = 0.0
    equity_curve = [{"trade": 0, "equity": equity, "date": trades[0]["entry_date"] if trades else ""}]

    for i, t in enumerate(trades, 1):
        equity += t["pnl_amount"]
        if equity > peak:
            peak = equity
        dd = ((peak - equity) / peak) * 100.0 if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
        equity_curve.append({
            "trade": i,
            "equity": round(equity, 0),
            "date": t.get("exit_date", t.get("entry_date", ""))
        })

    # Breakdown by Setup
    def _metrics_for_setup(setup_name: str) -> Dict[str, Any]:
        subset = [t for t in trades if t.get("setup") == setup_name]
        cnt = len(subset)
        if cnt == 0:
            return {"trades": 0, "win_rate": 0.0, "profit_factor": 0.0, "avg_r": 0.0}
        w = [t for t in subset if t["result"] == "WIN"]
        l = [t for t in subset if t["result"] == "LOSS"]
        wr = round((len(w) / cnt) * 100.0, 1)
        gp = sum(t["pnl_amount"] for t in w)
        gl = sum(abs(t["pnl_amount"]) for t in l)
        pf = round(gp / gl, 2) if gl > 0 else (999.0 if gp > 0 else 0.0)
        ar = round(sum(t.get("r_multiple", 0.0) for t in subset) / cnt, 2)
        return {"trades": cnt, "win_rate": wr, "profit_factor": pf, "avg_r": ar}

    return {
        "total_trades": total_trades,
        "wins": win_count,
        "losses": loss_count,
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "avg_r": avg_r,
        "max_drawdown": round(max_dd, 1),
        "pullback_metrics": _metrics_for_setup("PULLBACK"),
        "breakout_metrics": _metrics_for_setup("BREAKOUT"),
        "setup_breakdown": {
            "PULLBACK": _metrics_for_setup("PULLBACK"),
            "BREAKOUT": _metrics_for_setup("BREAKOUT")
        },
        "equity_curve": equity_curve
    }
