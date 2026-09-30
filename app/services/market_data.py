import time
import os
import logging
import datetime
import pytz
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import yfinance as yf
import pandas as pd
from sqlalchemy.orm import Session
from app.database import repositories, models

# Setup file logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename="logs/app.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("market_data")
TZ_JAKARTA = pytz.timezone("Asia/Jakarta")


def _fetch_direct_chart(ticker: str, period: str = "5d") -> pd.DataFrame:
    """
    Direct HTTP request to Yahoo Finance chart API.
    Bypasses yfinance crumb rate-limiting (HTTP 429) on cloud datacenter IPs.
    """
    range_map = {"5d": "5d", "1y": "1y", "1mo": "1mo", "6mo": "6mo"}
    r_val = range_map.get(period, "1y")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }

    # 1. Try direct Yahoo Chart JSON API (Never requires crumb authentication)
    for host in ["query1.finance.yahoo.com", "query2.finance.yahoo.com"]:
        try:
            url = f"https://{host}/v8/finance/chart/{ticker}?range={r_val}&interval=1d"
            res = requests.get(url, headers=headers, timeout=8)
            if res.status_code == 200:
                data = res.json()
                results = data.get("chart", {}).get("result")
                if results and len(results) > 0:
                    r0 = results[0]
                    timestamps = r0.get("timestamp", [])
                    quote_indicators = r0.get("indicators", {}).get("quote", [{}])[0]
                    if timestamps and quote_indicators:
                        dates = [datetime.datetime.fromtimestamp(ts, tz=TZ_JAKARTA) for ts in timestamps]
                        df = pd.DataFrame({
                            "Open": quote_indicators.get("open", []),
                            "High": quote_indicators.get("high", []),
                            "Low": quote_indicators.get("low", []),
                            "Close": quote_indicators.get("close", []),
                            "Volume": quote_indicators.get("volume", []),
                        }, index=pd.DatetimeIndex(dates))
                        df = df.dropna(subset=["Close"])
                        if not df.empty:
                            return df
        except Exception as e:
            logger.debug(f"Direct chart error {host} for {ticker}: {e}")
            continue

    # 2. Fallback to standard yfinance if direct API fails
    try:
        t = yf.Ticker(ticker)
        df_yf = t.history(period=period, interval="1d", auto_adjust=False)
        if df_yf is not None and not df_yf.empty:
            df_yf = df_yf.dropna(how="all")
            if not df_yf.empty:
                if df_yf.index.tz is not None:
                    df_yf.index = df_yf.index.tz_convert(TZ_JAKARTA)
                else:
                    df_yf.index = df_yf.index.tz_localize("UTC").tz_convert(TZ_JAKARTA)
                return df_yf
    except Exception as e:
        logger.debug(f"yfinance fallback error for {ticker}: {e}")

    return pd.DataFrame()


def update_market_data(db: Session, progress_callback=None, max_workers: int = 10):
    """
    High-performance parallel market data updater.
    - Uses Direct Yahoo Chart API (never blocked by crumb rate-limits on VPS).
    - 10 concurrent network workers for ~1 minute complete sync.
    - Smart incremental sync: symbols with existing prices in DB fetch period='5d' (fast).
      Symbols with no history fetch period='1y' (initial sync).
    - Database writes are serialized via thread lock for 100% thread safety.
    """
    symbols = repositories.get_active_symbols(db)
    if not symbols:
        return {"total": 0, "success": 0, "errors": 0}

    total = len(symbols)

    # 1. Pre-query existing symbol IDs with data for smart incremental fetching
    try:
        existing_symbol_ids = set(
            r[0] for r in db.query(models.DailyPrice.symbol_id).distinct().all()
        )
    except Exception as e:
        logger.warning(f"Could not check existing symbol prices: {e}")
        existing_symbol_ids = set()

    # 2. Extract plain primitives to avoid SQLAlchemy ORM lazy-loading across threads
    items = [
        (s.id, s.symbol, "5d" if s.id in existing_symbol_ids else "1y")
        for s in symbols
    ]

    logger.info(f"Starting parallel market data update for {total} symbols ({max_workers} threads)...")
    print(f"Starting parallel market data update for {total} symbols ({max_workers} threads)...")

    completed = 0
    success = 0
    errors = 0
    db_lock = threading.Lock()

    def fetch_worker(item):
        sym_id, ticker_str, period = item
        df = _fetch_direct_chart(ticker_str, period=period)
        if not df.empty:
            return sym_id, ticker_str, df, None
        return sym_id, ticker_str, None, "no_data"

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(fetch_worker, item): item for item in items}

        for future in as_completed(future_map):
            completed += 1

            if progress_callback:
                progress_callback(completed, total)

            try:
                sym_id, ticker_str, df, err = future.result()
                if df is not None and not df.empty:
                    with db_lock:
                        repositories.save_daily_prices(db, sym_id, df)
                    success += 1
                else:
                    errors += 1
            except Exception as ex:
                errors += 1
                logger.error(f"Error processing future result for {ticker_str}: {ex}")

            if completed % 100 == 0 or completed == total:
                logger.info(f"Market data progress: {completed}/{total} ({success} success, {errors} errors)")

    if progress_callback:
        progress_callback(total, total)

    logger.info(f"Market data update finished. Success: {success}/{total}, Errors: {errors}")
    return {"total": total, "success": success, "errors": errors}
