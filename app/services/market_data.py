"""
Market Data Updater — TradingView Edition
==========================================
Strategi dua tahap yang bebas dari Yahoo Finance 429:

TAHAP 1 — Bulk update candle hari ini (super cepat, ~2 detik total):
  → TradingView Indonesia Scanner: 1 request → data 891 saham sekaligus
  → Untuk saham yang sudah punya history di DB: cukup upsert candle hari ini

TAHAP 2 — Fetch history penuh untuk saham baru (sekali saja):
  → tvdatafeed (TradingView WebSocket): 500 candle historis per saham
  → Dijalankan dengan ThreadPoolExecutor (5 worker paralel)
  → Setelah semua saham punya history, tahap ini akan dilewati

Hasil: Update harian yang sebelumnya ~15 menit sekarang ~2 detik setelah
setup awal. Sama sekali tidak menyentuh Yahoo Finance.
"""

import time
import os
import logging
import datetime
import pytz
import threading
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy.orm import Session

from app.database import repositories, models
from app.providers.tradingview import (
    fetch_scanner_bulk_ohlcv,
    fetch_tvdatafeed_history,
    _to_idx_ticker,
)

# ── Logging setup ─────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename="logs/app.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("market_data")
TZ_JAKARTA = pytz.timezone("Asia/Jakarta")


def _make_today_df(ohlcv: dict) -> pd.DataFrame:
    """
    Buat DataFrame satu baris berisi data hari ini dari scanner.
    Format kolom sesuai repositories.save_daily_prices (Open, High, Low, Close, Volume).
    """
    today = datetime.datetime.now(TZ_JAKARTA).date()
    ts = pd.Timestamp(
        datetime.datetime.combine(today, datetime.time.min),
        tz=TZ_JAKARTA
    )
    return pd.DataFrame(
        [{
            "Open":   ohlcv["open"],
            "High":   ohlcv["high"],
            "Low":    ohlcv["low"],
            "Close":  ohlcv["close"],
            "Volume": ohlcv["volume"],
        }],
        index=pd.DatetimeIndex([ts])
    )


def update_market_data(db: Session, progress_callback=None, max_workers: int = 5):
    """
    Update data pasar seluruh saham IDX.

    Args:
        db               : SQLAlchemy session
        progress_callback: fn(current: int, total: int) — dipanggil setiap saham selesai
        max_workers      : jumlah thread paralel untuk tvdatafeed (default 5)

    Returns:
        dict: {'total': int, 'success': int, 'errors': int, 'history_fetched': int}
    """
    symbols = repositories.get_active_symbols(db)
    if not symbols:
        return {"total": 0, "success": 0, "errors": 0, "history_fetched": 0}

    total = len(symbols)
    logger.info(f"=== Mulai update market data: {total} saham ===")

    # ── Cek saham mana yang sudah punya history di DB ─────────────────────────
    try:
        existing_symbol_ids = set(
            r[0] for r in db.query(models.DailyPrice.symbol_id).distinct().all()
        )
    except Exception as e:
        logger.warning(f"Gagal cek existing symbols: {e}")
        existing_symbol_ids = set()

    logger.info(
        f"Saham dengan history di DB: {len(existing_symbol_ids)} / {total}"
    )

    # ── TAHAP 1: Bulk fetch OHLCV hari ini dari TradingView Scanner ───────────
    logger.info("TAHAP 1: Mengambil data dari TradingView Scanner...")
    scanner_data = fetch_scanner_bulk_ohlcv(limit=1000)
    logger.info(f"Scanner mengembalikan {len(scanner_data)} saham")

    success = 0
    errors = 0
    history_fetched = 0
    db_lock = threading.Lock()

    # Pisahkan: saham yang butuh history penuh vs cukup update hari ini
    need_history: list = []

    for idx, sym in enumerate(symbols, 1):
        if progress_callback:
            progress_callback(idx, total)

        idx_ticker = _to_idx_ticker(sym.symbol)
        scanner_row = scanner_data.get(idx_ticker)

        if sym.id in existing_symbol_ids:
            # Sudah ada history — upsert candle hari ini saja
            if scanner_row:
                try:
                    today_df = _make_today_df(scanner_row)
                    repositories.save_daily_prices(db, sym.id, today_df)
                    success += 1
                except Exception as e:
                    errors += 1
                    logger.error(f"Error save scanner candle {sym.symbol}: {e}")
            else:
                # Scanner tidak punya data saham ini (mungkin suspend/delisting)
                errors += 1
                logger.debug(f"Scanner: tidak ada data untuk {sym.symbol}")
        else:
            # Belum ada history — perlu fetch penuh via tvdatafeed
            need_history.append((sym, scanner_row))

    logger.info(
        f"TAHAP 1 selesai. Update hari ini: {success} berhasil, {errors} gagal. "
        f"Saham baru butuh history: {len(need_history)}"
    )

    # ── TAHAP 2: Fetch history penuh untuk saham baru via tvdatafeed ──────────
    if need_history:
        logger.info(
            f"TAHAP 2: Fetch history penuh {len(need_history)} saham via tvdatafeed "
            f"({max_workers} thread paralel)..."
        )

        def fetch_worker(item):
            sym, scanner_row = item
            df = fetch_tvdatafeed_history(sym.symbol, n_bars=500)
            return sym.id, sym.symbol, df, scanner_row

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(fetch_worker, item): item for item in need_history
            }
            done_count = 0
            for future in as_completed(future_map):
                done_count += 1
                try:
                    sym_id, ticker_str, df, scanner_row = future.result()

                    saved = False
                    # Simpan history dari tvdatafeed
                    if df is not None and not df.empty:
                        with db_lock:
                            repositories.save_daily_prices(db, sym_id, df)
                        history_fetched += 1
                        saved = True

                    # Tambahkan / update candle hari ini dari scanner (jika ada)
                    if scanner_row:
                        try:
                            today_df = _make_today_df(scanner_row)
                            with db_lock:
                                repositories.save_daily_prices(db, sym_id, today_df)
                        except Exception as e:
                            logger.debug(f"Error upsert today candle {ticker_str}: {e}")

                    if saved:
                        success += 1
                    else:
                        errors += 1
                        logger.warning(f"Tidak ada data history untuk {ticker_str}")

                except Exception as ex:
                    errors += 1
                    logger.error(f"Error fetch history: {ex}")

                if done_count % 50 == 0 or done_count == len(need_history):
                    logger.info(
                        f"tvdatafeed progress: {done_count}/{len(need_history)} "
                        f"({history_fetched} berhasil)"
                    )

    # ── Selesai ───────────────────────────────────────────────────────────────
    if progress_callback:
        progress_callback(total, total)

    result = {
        "total":           total,
        "success":         success,
        "errors":          errors,
        "history_fetched": history_fetched,
    }
    logger.info(
        f"=== Market data update selesai. "
        f"Berhasil: {success}/{total}, Gagal: {errors}, "
        f"History baru: {history_fetched} ==="
    )
    return result
