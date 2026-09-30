import pandas as pd
import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.database import repositories
from app.indicators import trend, momentum, volume
from app.strategy.signal_engine import evaluate_signal
from app.backtest.metrics import calculate_backtest_metrics
from app import config

class BacktestEngine:
    def __init__(self, db: Session, max_hold_days: int = 5):
        self.db = db
        self.max_hold_days = max_hold_days

    def run(
        self, 
        selected_symbols: Optional[List[str]] = None,
        setup_filter: str = "ALL",  # 'ALL', 'PULLBACK', 'BREAKOUT'
        min_score: int = 70,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Runs backtest with strict no-look-ahead bias on historical candle data.
        """
        all_symbols = repositories.get_active_symbols(self.db)
        if selected_symbols:
            symbols = [s for s in all_symbols if s.symbol in selected_symbols]
        else:
            symbols = all_symbols

        trades: List[Dict[str, Any]] = []

        for sym in symbols:
            # Load full price history for symbol
            records = repositories.get_all_daily_prices(self.db, sym.id)
            if len(records) < 30:
                continue

            df = pd.DataFrame([{
                'date': r.date,
                'open': float(r.open),
                'high': float(r.high),
                'low': float(r.low),
                'close': float(r.close),
                'volume': float(r.volume)
            } for r in records]).sort_values('date').reset_index(drop=True)

            # Pre-calculate indicators on full series
            df = trend.add_trend_indicators(df)
            df = momentum.add_momentum_indicators(df)
            df = volume.add_volume_indicators(df)

            in_position = False
            active_trade = None

            # Iterate candle by candle to prevent look-ahead bias
            # Start after 25 warmup candles
            for t in range(25, len(df)):
                current_candle = df.iloc[t]
                current_date = current_candle['date']
                date_str = str(current_date)[:10]

                # Date filtering
                if start_date and date_str < start_date:
                    continue
                if end_date and date_str > end_date:
                    break

                # 1. Manage Active Trade
                if in_position and active_trade:
                    high = current_candle['high']
                    low = current_candle['low']
                    close = current_candle['close']
                    days_held = t - active_trade["entry_index"]

                    # Check Stop Loss hit first (conservative assumption)
                    if low <= active_trade["stop_loss"]:
                        exit_price = active_trade["stop_loss"]
                        pnl_pct = ((exit_price - active_trade["entry_price"]) / active_trade["entry_price"]) * 100.0
                        pnl_amount = (exit_price - active_trade["entry_price"]) * active_trade["shares"]
                        risk_per_share = max(1.0, active_trade["entry_price"] - active_trade["stop_loss"])
                        r_multiple = round((exit_price - active_trade["entry_price"]) / risk_per_share, 2)

                        active_trade.update({
                            "exit_date": date_str,
                            "exit_price": round(exit_price, 2),
                            "result": "LOSS",
                            "pnl_pct": round(pnl_pct, 2),
                            "pnl_amount": round(pnl_amount, 2),
                            "r_multiple": r_multiple,
                            "exit_reason": "Stop Loss Hit",
                            "days_held": days_held
                        })
                        trades.append(active_trade)
                        in_position = False
                        active_trade = None
                        continue

                    # Check Take Profit 1 / 2 hit
                    elif high >= active_trade["tp1"]:
                        exit_price = active_trade["tp1"]
                        pnl_pct = ((exit_price - active_trade["entry_price"]) / active_trade["entry_price"]) * 100.0
                        pnl_amount = (exit_price - active_trade["entry_price"]) * active_trade["shares"]
                        risk_per_share = max(1.0, active_trade["entry_price"] - active_trade["stop_loss"])
                        r_multiple = round((exit_price - active_trade["entry_price"]) / risk_per_share, 2)

                        active_trade.update({
                            "exit_date": date_str,
                            "exit_price": round(exit_price, 2),
                            "result": "WIN",
                            "pnl_pct": round(pnl_pct, 2),
                            "pnl_amount": round(pnl_amount, 2),
                            "r_multiple": r_multiple,
                            "exit_reason": "Take Profit Hit",
                            "days_held": days_held
                        })
                        trades.append(active_trade)
                        in_position = False
                        active_trade = None
                        continue

                    # Check Max Holding Period reached (Day trade / Swing timeout)
                    elif days_held >= self.max_hold_days:
                        exit_price = close
                        pnl_pct = ((exit_price - active_trade["entry_price"]) / active_trade["entry_price"]) * 100.0
                        pnl_amount = (exit_price - active_trade["entry_price"]) * active_trade["shares"]
                        risk_per_share = max(1.0, active_trade["entry_price"] - active_trade["stop_loss"])
                        r_multiple = round((exit_price - active_trade["entry_price"]) / risk_per_share, 2)
                        result = "WIN" if pnl_pct > 0 else "LOSS"

                        active_trade.update({
                            "exit_date": date_str,
                            "exit_price": round(exit_price, 2),
                            "result": result,
                            "pnl_pct": round(pnl_pct, 2),
                            "pnl_amount": round(pnl_amount, 2),
                            "r_multiple": r_multiple,
                            "exit_reason": f"Time Exit ({days_held}d)",
                            "days_held": days_held
                        })
                        trades.append(active_trade)
                        in_position = False
                        active_trade = None
                        continue

                # 2. Check for New Signal (using strictly past slice up to t)
                if not in_position:
                    slice_df = df.iloc[:t+1]
                    sig = evaluate_signal(slice_df)

                    if sig["score"] >= min_score and sig["status"] == "READY":
                        if setup_filter != "ALL" and sig["setup"] != setup_filter:
                            continue
                        
                        entry_price = float(current_candle['close'])
                        stop_loss = float(sig['stop_loss'])
                        tp1 = float(sig['tp1'])
                        tp2 = float(sig['tp2'])

                        if entry_price > stop_loss and tp1 > entry_price:
                            # Position sizing: risk 1% of 100M capital = 1,000,000 IDR risk
                            risk_per_share = entry_price - stop_loss
                            shares = int(1_000_000 / risk_per_share) if risk_per_share > 0 else 100
                            shares = max(100, (shares // 100) * 100) # Lot size 100 in IDX

                            in_position = True
                            active_trade = {
                                "symbol": sym.symbol,
                                "name": sym.name,
                                "setup": sig["setup"],
                                "score": sig["score"],
                                "grade": sig["grade"],
                                "entry_date": date_str,
                                "entry_index": t,
                                "entry_price": entry_price,
                                "stop_loss": stop_loss,
                                "tp1": tp1,
                                "tp2": tp2,
                                "shares": shares,
                                "risk_reward": sig["risk_reward"]
                            }

        # Sort all completed trades by exit date / entry date
        trades.sort(key=lambda x: x.get("entry_date", ""))
        metrics = calculate_backtest_metrics(trades)

        return {
            "metrics": metrics,
            "trades": trades,
            "total_trades_count": len(trades),
            "start_date": start_date or (trades[0]["entry_date"] if trades else ""),
            "end_date": end_date or (trades[-1]["exit_date"] if trades else "")
        }
