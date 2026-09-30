"""
Market Data Updater — TradingView Scanner Edition (v2)
=======================================================
Strategi baru yang sepenuhnya menghindari Yahoo Finance 429:

SATU REQUEST → semua 891 saham IDX:
  TradingView Scanner mengembalikan OHLCV hari ini + indikator pre-computed
  (RSI14, EMA9, EMA20, EMA50, ATR, Volume_MA30, Pivot S1/R1)

Keuntungan vs approach lama (tvdatafeed per-stock):
  - Tidak ada WebSocket / rate-limit per stock
  - Semua 891 saham selesai dalam ~2 detik
  - Indikator sudah dihitung oleh TradingView (akurat, sama dengan chart TV)
  - Bisa langsung dipakai oleh evaluate_signal_from_scanner()

tvdatafeed TETAP digunakan untuk:
  - Halaman detail /stock/{symbol} → chart historis per saham on-demand
  - Backtest (butuh candle series)
"""

import os
import logging
import datetime
import pytz
import pandas as pd
import requests
from sqlalchemy.orm import Session

from app.database import repositories, models

# ── Logging ──────────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename="logs/app.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("market_data")
TZ_JAKARTA = pytz.timezone("Asia/Jakarta")

TV_SCANNER_URL = "https://scanner.tradingview.com/indonesia/scan"
_TV_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Kolom yang kita minta dari TradingView Scanner (urutan ini PENTING)
SCANNER_COLUMNS = [
    "name",                    # 0  ticker IDX (e.g. BBCA)
    "open",                    # 1  open hari ini
    "high",                    # 2  high hari ini
    "low",                     # 3  low hari ini
    "close",                   # 4  close/last price
    "volume",                  # 5  volume hari ini
    "change",                  # 6  % change
    "change_abs",              # 7  absolute change (Rp)
    "RSI",                     # 8  RSI14 (pre-computed by TV)
    "EMA9",                    # 9  EMA9
    "EMA20",                   # 10 EMA20 (TV pakai EMA20, kita rename ke EMA21)
    "EMA50",                   # 11 EMA50
    "SMA20",                   # 12 SMA20 (= MA20)
    "SMA50",                   # 13 SMA50 (= MA50)
    "ATR",                     # 14 ATR14
    "average_volume_30d_calc", # 15 volume rata-rata 30 hari
    "Pivot.M.Classic.S1",      # 16 support level pivot
    "Pivot.M.Classic.R1",      # 17 resistance level pivot
]

# Index column dalam list SCANNER_COLUMNS
COL = {name: idx for idx, name in enumerate(SCANNER_COLUMNS)}


def fetch_all_scanner_data(limit: int = 1000) -> dict:
    """
    Ambil OHLCV + indikator untuk SEMUA saham IDX dalam satu request.

    Return: {
      'BBCA': {
        'open': 9200, 'high': 9300, 'low': 9150, 'close': 9250,
        'volume': 12000000, 'change_pct': 0.54, 'change_abs': 50.0,
        'rsi': 58.2, 'ema9': 9180.0, 'ema20': 9100.0, 'ema50': 8950.0,
        'ma20': 9095.0, 'ma50': 8940.0, 'atr': 120.0,
        'avg_vol_30d': 8500000.0, 'support': 9050.0, 'resistance': 9500.0
      }, ...
    }
    """
    payload = {
        "filter": [],
        "options": {"lang": "en"},
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": SCANNER_COLUMNS,
        "sort": {"sortBy": "volume", "sortOrder": "desc"},
        "range": [0, limit]
    }
    result = {}
    try:
        r = requests.post(TV_SCANNER_URL, json=payload, headers=_TV_HEADERS, timeout=20)
        r.raise_for_status()
        total = r.json().get("totalCount", 0)
        for item in r.json().get("data", []):
            d = item.get("d", [])
            if len(d) < len(SCANNER_COLUMNS):
                continue
            name = d[COL["name"]]
            close = d[COL["close"]]
            if not name or close is None:
                continue

            def _f(key, fallback=None):
                v = d[COL[key]]
                return float(v) if v is not None else fallback

            result[name] = {
                "open":        _f("open",  close),
                "high":        _f("high",  close),
                "low":         _f("low",   close),
                "close":       float(close),
                "volume":      _f("volume", 0.0),
                "change_pct":  _f("change", 0.0),
                "change_abs":  _f("change_abs", 0.0),
                "rsi":         _f("RSI", 50.0),
                "ema9":        _f("EMA9", close),
                "ema20":       _f("EMA20", close),   # TradingView EMA20 ≈ kita sebut EMA21
                "ema50":       _f("EMA50", close),
                "ma20":        _f("SMA20", close),
                "ma50":        _f("SMA50", close),
                "atr":         _f("ATR", close * 0.02),
                "avg_vol_30d": _f("average_volume_30d_calc", 0.0),
                "support":     _f("Pivot.M.Classic.S1", close * 0.97),
                "resistance":  _f("Pivot.M.Classic.R1", close * 1.03),
            }
        logger.info(f"TradingView Scanner: {len(result)}/{total} saham dimuat")
    except Exception as e:
        logger.error(f"TradingView Scanner fetch error: {e}")
    return result


def _make_today_df(ohlcv: dict) -> pd.DataFrame:
    """Buat DataFrame 1 baris untuk simpan ke daily_prices."""
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


def _to_idx_ticker(ticker_jk: str) -> str:
    """BBCA.JK → BBCA"""
    return ticker_jk.upper().replace(".JK", "").replace(".IDX", "")


def update_market_data(db: Session, progress_callback=None, max_workers: int = 5):
    """
    Update market data semua saham IDX.

    SATU request ke TradingView Scanner → OHLCV + indikator semua saham.
    Simpan ke daily_prices sebagai candle hari ini.
    Saham yang tidak ada di scanner tetap tersimpan sebagai kosong.

    Returns: {'total': int, 'success': int, 'errors': int}
    """
    symbols = repositories.get_active_symbols(db)
    if not symbols:
        return {"total": 0, "success": 0, "errors": 0}

    total = len(symbols)
    logger.info(f"=== Update market data mulai: {total} saham ===")

    # Satu request untuk semua saham
    logger.info("Mengambil data dari TradingView Scanner...")
    scanner_data = fetch_all_scanner_data(limit=1000)
    logger.info(f"Scanner: {len(scanner_data)} saham diterima")

    success = 0
    errors = 0

    for idx, sym in enumerate(symbols, 1):
        if progress_callback:
            progress_callback(idx, total)

        idx_ticker = _to_idx_ticker(sym.symbol)
        row = scanner_data.get(idx_ticker)

        if row:
            try:
                today_df = _make_today_df(row)
                repositories.save_daily_prices(db, sym.id, today_df)
                success += 1
            except Exception as e:
                errors += 1
                logger.error(f"Error save {sym.symbol}: {e}")
        else:
            errors += 1
            logger.debug(f"Scanner tidak punya data untuk {sym.symbol}")

    if progress_callback:
        progress_callback(total, total)

    logger.info(f"=== Selesai: {success}/{total} berhasil, {errors} gagal ===")
    return {"total": total, "success": success, "errors": errors, "scanner_count": len(scanner_data)}


def get_scanner_data_for_symbol(ticker_jk: str) -> dict:
    """
    Ambil data scanner untuk satu saham (untuk halaman detail).
    Dipakai jika daily_prices kosong.
    """
    idx_ticker = _to_idx_ticker(ticker_jk)
    payload = {
        "filter": [{"left": "name", "operation": "equal", "right": idx_ticker}],
        "options": {"lang": "en"},
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": SCANNER_COLUMNS,
        "range": [0, 1]
    }
    try:
        r = requests.post(TV_SCANNER_URL, json=payload, headers=_TV_HEADERS, timeout=8)
        r.raise_for_status()
        data = r.json().get("data", [])
        if data:
            d = data[0]["d"]
            name = d[COL["name"]]
            close = d[COL["close"]]

            def _f(key, fallback=None):
                v = d[COL[key]]
                return float(v) if v is not None else fallback

            return {
                "open":        _f("open", close),
                "high":        _f("high", close),
                "low":         _f("low",  close),
                "close":       float(close),
                "volume":      _f("volume", 0.0),
                "change_pct":  _f("change", 0.0),
                "change_abs":  _f("change_abs", 0.0),
                "rsi":         _f("RSI", 50.0),
                "ema9":        _f("EMA9", close),
                "ema20":       _f("EMA20", close),
                "ema50":       _f("EMA50", close),
                "ma20":        _f("SMA20", close),
                "ma50":        _f("SMA50", close),
                "atr":         _f("ATR", float(close) * 0.02),
                "avg_vol_30d": _f("average_volume_30d_calc", 0.0),
                "support":     _f("Pivot.M.Classic.S1", float(close) * 0.97),
                "resistance":  _f("Pivot.M.Classic.R1", float(close) * 1.03),
            }
    except Exception as e:
        logger.error(f"Scanner single quote error {ticker_jk}: {e}")
    return {}
