import pandas as pd
import datetime
import logging
import math
import pytz
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional

from app.database import repositories
from app.indicators import trend, momentum, volume
from app.scanner import screener, ranking
from app.strategy.signal_engine import evaluate_signal, evaluate_signal_from_scanner
from app.services.market_data import fetch_all_scanner_data, _to_idx_ticker
from app.providers.tradingview import TradingViewProvider
from app import config

logger = logging.getLogger("app")

TZ_JAKARTA = pytz.timezone("Asia/Jakarta")
_provider = TradingViewProvider()


def _safe(v, default=0.0):
    """Return a finite float or default — never NaN/Inf."""
    try:
        f = float(v)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def load_symbol_dataframe(db: Session, symbol_id: int, limit: int = 250) -> pd.DataFrame:
    records = repositories.get_recent_daily_prices(db, symbol_id, limit=limit)
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame([{
        'date': r.date,
        'open': float(r.open),
        'high': float(r.high),
        'low': float(r.low),
        'close': float(r.close),
        'volume': float(r.volume)
    } for r in records])

    # Sort by date ascending for sequential indicator calculation
    df = df.sort_values('date').reset_index(drop=True)

    # Apply all technical indicators
    df = trend.add_trend_indicators(df)
    df = momentum.add_momentum_indicators(df)
    df = volume.add_volume_indicators(df)

    return df


def process_symbol_detail(db: Session, ticker: str) -> Optional[Dict[str, Any]]:
    """Calculates all indicators and strategy signal for a single stock."""
    symbol_record = repositories.get_symbol_by_ticker(db, ticker)
    if not symbol_record:
        return None

    df = load_symbol_dataframe(db, symbol_record.id)
    if df.empty:
        now_jkt = datetime.datetime.now(TZ_JAKARTA)
        return {
            "symbol": symbol_record.symbol,
            "name": symbol_record.name,
            "sector": symbol_record.sector,
            "status": "DATA_UNAVAILABLE",
            "score": 0,
            "grade": "NO TRADE",
            "setup": "NONE",
            "entry_validity": "UNKNOWN",
            "freshness": "UNKNOWN",
            "next_action": "MONITOR",
            "primary_reason": "Belum ada data historis. Klik Perbarui Data terlebih dahulu.",
            "signal_age_minutes": 0,
            "signal_generated_at": now_jkt.isoformat(),
            "signal_generated_str": now_jkt.strftime("%d %b %Y %H:%M WIB"),
            "candles": [],
            "why_this_stock": [],
            "why_not_ready": ["Belum ada data historis. Klik Perbarui Data terlebih dahulu."]
        }

    # ── Daily candle data ─────────────────────────────────────────────────────
    latest = df.iloc[-1]
    daily_close = _safe(latest['close'])

    # ── Live quote (TradingView Scanner) ────────────────────────────────────
    quote = _provider.get_quote(ticker)
    current_price = quote.get("current_price") or daily_close
    previous_close = quote.get("previous_close") or daily_close
    day_high = quote.get("day_high")
    day_low = quote.get("day_low")

    now_jkt = datetime.datetime.now(TZ_JAKARTA)
    signal_result = evaluate_signal(df, reference_price=current_price, signal_time=now_jkt)
    passed_screener = screener.run_base_screener(df)

    change_pct = 0.0
    if previous_close and previous_close > 0:
        change_pct = round((current_price - previous_close) / previous_close * 100, 2)

    candles = []
    for _, row in df.iterrows():
        dt_str = row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date'])[:10]
        candles.append({
            "time": dt_str,
            "open": round(row['open'], 2),
            "high": round(row['high'], 2),
            "low": round(row['low'], 2),
            "close": round(row['close'], 2),
            "volume": int(row['volume']),
            "ema9": round(row['EMA9'], 2) if 'EMA9' in row and not pd.isna(row['EMA9']) else None,
            "ema21": round(row['EMA21'], 2) if 'EMA21' in row and not pd.isna(row['EMA21']) else None,
            "rsi": round(row['RSI14'], 2) if 'RSI14' in row and not pd.isna(row['RSI14']) else None
        })

    result = {
        "symbol": symbol_record.symbol,
        "name": symbol_record.name,
        "sector": symbol_record.sector,
        "passed_screener": passed_screener,
        "candles": candles,
        "latest_date": str(latest['date'])[:10],
        "current_price": round(current_price, 2),
        "previous_close": round(previous_close, 2),
        "daily_close": round(daily_close, 2),
        "day_high": round(day_high, 2) if day_high else None,
        "day_low": round(day_low, 2) if day_low else None,
        "change_pct": change_pct,
        "price_source": quote.get("data_source", "TradingView Scanner"),
        "price_note": quote.get("data_note", ""),
        "quote_timestamp": quote.get("quote_timestamp", ""),
        **signal_result
    }
    return result


def run_scanner(db: Session, progress_callback=None) -> Dict[str, Any]:
    """
    Jalankan screener & ranking untuk SEMUA saham aktif.

    Strategi dua jalur:
    1. Saham dengan ≥ 5 candle di DB: gunakan evaluate_signal() historis (akurat penuh)
    2. Saham dengan < 5 candle / tanpa data: gunakan evaluate_signal_from_scanner()
       dengan data pre-computed dari TradingView Scanner

    Dengan ini, SEMUA 934 saham akan muncul dalam hasil scan —
    tidak ada saham yang di-skip karena kurang data.
    """
    scan_run = repositories.create_scan_run(db)
    symbols = repositories.get_active_symbols(db)
    total_symbols = len(symbols)
    scan_time = scan_run.started_at or datetime.datetime.now(datetime.timezone.utc)

    # ── Ambil data scanner untuk semua saham (1 request) ────────────────────
    logger.info("run_scanner: mengambil data TradingView Scanner untuk semua saham...")
    scanner_data = fetch_all_scanner_data(limit=1000)
    logger.info(f"run_scanner: scanner mengembalikan {len(scanner_data)} saham")

    all_results = []
    passed_results = []
    error_count = 0

    for idx, sym in enumerate(symbols, start=1):
        if progress_callback:
            progress_callback(idx, total_symbols)
        try:
            df = load_symbol_dataframe(db, sym.id)
            idx_ticker = _to_idx_ticker(sym.symbol)
            scanner_row = scanner_data.get(idx_ticker)

            has_history = not df.empty and len(df) >= 5

            # ── Pilih metode evaluasi ────────────────────────────────────────
            if has_history:
                # Metode 1: historical OHLCV + compute indicators (akurat)
                latest = df.iloc[-1]
                daily_close = _safe(latest['close'])
                sig = evaluate_signal(df, signal_time=scan_time)

                item = {
                    "symbol_id":  sym.id,
                    "symbol":     sym.symbol,
                    "name":       sym.name,
                    "daily_close": daily_close,
                    "price":      daily_close,
                    "volume":     _safe(latest['volume']),
                    "rsi":        _safe(sig.get('rsi')),
                    "vol_ratio":  _safe(sig.get('volume_ratio')),
                    "est_value":  _safe(sig.get('est_value')),
                    "score":      int(sig.get('score', 0)),
                    "grade":      sig.get('grade', 'NO TRADE'),
                    "setup":      sig.get('setup', 'NONE'),
                    "status":     sig.get('status', 'NO_TRADE'),
                    "entry_zone": sig.get('entry_zone', '-'),
                    "entry_low":  _safe(sig.get('entry_low')),
                    "entry_high": _safe(sig.get('entry_high')),
                    "stop_loss":  _safe(sig.get('stop_loss')),
                    "tp1":        _safe(sig.get('tp1')),
                    "tp2":        _safe(sig.get('tp2')),
                    "risk_reward": _safe(sig.get('risk_reward')),
                    "dist_ema9_pct": _safe(sig.get('dist_ema9_pct')),
                    "passed":     screener.run_base_screener(df),
                    "latest_date": str(latest['date'])[:10],
                    "data_timestamp": latest['date'],
                    "price_note": "Daily Close dari DB historis",
                    "primary_reason": sig.get("primary_reason", ""),
                    "entry_validity": sig.get("entry_validity", "VALID"),
                    "freshness":      sig.get("freshness", "FRESH"),
                    "signal_age_minutes": sig.get("signal_age_minutes", 0),
                    "signal_generated_at":  sig.get("signal_generated_at"),
                    "signal_generated_str": sig.get("signal_generated_str"),
                    "next_action": sig.get("next_action", "MONITOR"),
                    "data_source": "historical",
                }

            elif scanner_row:
                # Metode 2: TradingView Scanner pre-computed indicators
                sig = evaluate_signal_from_scanner(scanner_row)
                today_str = datetime.datetime.now(TZ_JAKARTA).strftime("%Y-%m-%d")

                item = {
                    "symbol_id":  sym.id,
                    "symbol":     sym.symbol,
                    "name":       sym.name,
                    "daily_close": scanner_row["close"],
                    "price":      scanner_row["close"],
                    "volume":     scanner_row["volume"],
                    "rsi":        scanner_row.get("rsi", 50.0),
                    "vol_ratio":  sig.get("volume_ratio", 1.0),
                    "est_value":  sig.get("est_value", 0.0),
                    "score":      int(sig.get('score', 0)),
                    "grade":      sig.get('grade', 'NO TRADE'),
                    "setup":      sig.get('setup', 'NONE'),
                    "status":     sig.get('status', 'NO_TRADE'),
                    "entry_zone": sig.get('entry_zone', '-'),
                    "entry_low":  sig.get('entry_low', 0.0),
                    "entry_high": sig.get('entry_high', 0.0),
                    "stop_loss":  sig.get('stop_loss', 0.0),
                    "tp1":        sig.get('tp1', 0.0),
                    "tp2":        sig.get('tp2', 0.0),
                    "risk_reward": sig.get('risk_reward', 0.0),
                    "dist_ema9_pct": sig.get('dist_ema9_pct', 0.0),
                    "passed":     False,  # Scanner-only data tidak masuk passed list
                    "latest_date": today_str,
                    "data_timestamp": datetime.datetime.now(TZ_JAKARTA),
                    "price_note": "Data real-time TradingView Scanner",
                    "primary_reason": sig.get("primary_reason", ""),
                    "entry_validity": sig.get("entry_validity", "VALID"),
                    "freshness":      "FRESH",
                    "signal_age_minutes": 0,
                    "signal_generated_at":  sig.get("signal_generated_at"),
                    "signal_generated_str": sig.get("signal_generated_str"),
                    "next_action": sig.get("next_action", "MONITOR"),
                    "data_source": "scanner",
                }

            else:
                # Tidak ada data sama sekali
                now_jkt = datetime.datetime.now(TZ_JAKARTA)
                item = {
                    "symbol_id":  sym.id,
                    "symbol":     sym.symbol,
                    "name":       sym.name,
                    "daily_close": 0.0,
                    "price":      0.0,
                    "volume":     0.0,
                    "rsi":        0.0,
                    "vol_ratio":  0.0,
                    "est_value":  0.0,
                    "score":      0,
                    "grade":      "NO TRADE",
                    "setup":      "NONE",
                    "status":     "DATA_UNAVAILABLE",
                    "entry_zone": "-",
                    "entry_low":  0.0, "entry_high": 0.0,
                    "stop_loss":  0.0, "tp1": 0.0, "tp2": 0.0,
                    "risk_reward": 0.0, "dist_ema9_pct": 0.0,
                    "passed":     False,
                    "latest_date": "-",
                    "data_timestamp": now_jkt,
                    "price_note": "Data tidak tersedia",
                    "primary_reason": "Tidak ada data dari DB maupun TradingView Scanner.",
                    "entry_validity": "UNKNOWN",
                    "freshness":      "UNKNOWN",
                    "signal_age_minutes": 0,
                    "signal_generated_at":  now_jkt.isoformat(),
                    "signal_generated_str": now_jkt.strftime("%d %b %Y %H:%M WIB"),
                    "next_action": "MONITOR",
                    "data_source": "none",
                }

            # Save signal ke DB (hanya untuk saham yang punya data nyata)
            if item["status"] not in ("DATA_UNAVAILABLE",) and item["price"] > 0:
                try:
                    repositories.save_signal(db, {
                        "symbol_id":   sym.id,
                        "price":       item["price"],
                        "score":       item["score"],
                        "grade":       item["grade"],
                        "setup":       item["setup"],
                        "status":      item["status"],
                        "entry_low":   item["entry_low"],
                        "entry_high":  item["entry_high"],
                        "stop_loss":   item["stop_loss"],
                        "tp1":         item["tp1"],
                        "tp2":         item["tp2"],
                        "risk_reward": item["risk_reward"],
                        "rsi":         item["rsi"],
                        "ema9":        _safe(scanner_row.get("ema9") if scanner_row else 0),
                        "ema21":       _safe(scanner_row.get("ema20") if scanner_row else 0),
                        "volume_ratio": item["vol_ratio"],
                        "est_value":   item["est_value"],
                        "reason":      item.get("primary_reason", ""),
                        "data_timestamp": item["data_timestamp"],
                    })
                except Exception as save_err:
                    logger.debug(f"Signal save error {sym.symbol}: {save_err}")

            all_results.append(item)
            if item.get("passed"):
                passed_results.append(item)

        except Exception as e:
            error_count += 1
            logger.error(f"Error scanning {sym.symbol}: {e}")

    # ── Filter dan ranking ─────────────────────────────────────────────────────
    ready_results = [
        dict(item) for item in all_results
        if item.get("status") == "READY" and item.get("score", 0) >= config.MIN_SIGNAL_SCORE
    ]
    passed_copies = [dict(item) for item in passed_results]
    all_copies    = [dict(item) for item in all_results]

    ranked_ready  = ranking.rank_candidates(ready_results)
    ranked_passed = ranking.rank_candidates(passed_copies)
    ranked_all    = ranking.rank_candidates(all_copies)

    wait_candidates = [
        r for r in all_copies
        if r.get("status") in ["WAIT_PULLBACK", "WAIT_BREAKOUT"] and r.get("score", 0) >= 65
    ]
    wait_candidates.sort(key=lambda x: x.get("score", 0), reverse=True)

    watch_candidates = [
        r for r in all_copies
        if r.get("status") == "WATCH" and r.get("score", 0) >= 60
    ]
    watch_candidates.sort(key=lambda x: x.get("score", 0), reverse=True)

    no_trade_candidates = [
        r for r in all_copies
        if r.get("status") in ["NO_TRADE", "DATA_UNAVAILABLE"]
    ]

    repositories.complete_scan_run(
        db,
        run_id=scan_run.id,
        scanned=len(symbols),
        passed=len(ranked_passed),
        errors=error_count
    )

    return {
        "ready_candidates": ranked_ready,
        "top_10":           ranked_ready,
        "wait_candidates":  wait_candidates,
        "watch_candidates": watch_candidates,
        "no_trade_candidates": no_trade_candidates,
        "passed":           ranked_passed,
        "all":              ranked_all,
        "scanned_count":    len(symbols),
        "ready_count":      len(ranked_ready),
        "passed_count":     len(ranked_passed),
        "wait_count":       len(wait_candidates),
        "watch_count":      len(watch_candidates),
        "no_trade_count":   len(no_trade_candidates),
        "a_plus_count":     len([r for r in ranked_ready if r.get('grade') == 'A+']),
        "a_count":          len([r for r in ranked_ready if r.get('grade') == 'A']),
        "a_plus_total":     len([r for r in all_copies if r.get('grade') == 'A+']),
        "a_total":          len([r for r in all_copies if r.get('grade') == 'A']),
        "scan_time":        scan_time.isoformat() if hasattr(scan_time, 'isoformat') else str(scan_time)
    }
