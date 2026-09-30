import time
import os
import logging
import pytz
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import yfinance as yf
import pandas as pd
from sqlalchemy.orm import Session
from app.database import repositories

# Setup file logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename="logs/app.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("market_data")
TZ_JAKARTA = pytz.timezone("Asia/Jakarta")


def _make_yf_session():
    """Create a requests session with browser-like headers and retry logic."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    })
    return session


def update_market_data(db: Session, progress_callback=None):
    """
    Fetches latest daily market data for all active symbols using individual
    ticker fetches with browser user-agent and retry logic to avoid 429 errors.
    """
    symbols = repositories.get_active_symbols(db)
    if not symbols:
        return {"total": 0, "success": 0, "errors": 0}

    total = len(symbols)
    success = 0
    errors = 0

    logger.info(f"Starting individual market data update for {total} symbols...")
    print(f"Starting individual market data update for {total} symbols...")

    for idx, sym in enumerate(symbols, 1):
        if progress_callback:
            progress_callback(idx, total)

        for attempt in range(3):
            try:
                ticker = yf.Ticker(sym.symbol)
                df = ticker.history(period='1y', interval='1d', auto_adjust=False)

                if df is not None and not df.empty:
                    df = df.dropna(how='all')
                    if not df.empty:
                        # Ensure timezone conversion to Asia/Jakarta
                        if df.index.tz is not None:
                            df.index = df.index.tz_convert(TZ_JAKARTA)
                        else:
                            df.index = df.index.tz_localize("UTC").tz_convert(TZ_JAKARTA)
                        repositories.save_daily_prices(db, sym.id, df)
                        success += 1
                        break
                    else:
                        errors += 1
                        break
                else:
                    errors += 1
                    break

            except Exception as e:
                if attempt == 2:
                    logger.error(f"Failed {sym.symbol} after 3 attempts: {e}")
                    errors += 1
                else:
                    wait = 2 ** attempt  # 1s, 2s
                    logger.debug(f"Retry {attempt + 1} for {sym.symbol} after {wait}s: {e}")
                    time.sleep(wait)

        # Polite delay between tickers to avoid rate limiting
        time.sleep(0.2)

        if idx % 50 == 0:
            logger.info(f"Progress: {idx}/{total} tickers processed. Success: {success}, Errors: {errors}")

    if progress_callback:
        progress_callback(total, total)

    logger.info(f"Market data update finished. Success: {success}/{total}, Errors: {errors}")
    return {"total": total, "success": success, "errors": errors}
