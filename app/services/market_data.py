import time
import os
import logging
import pytz
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

def update_market_data(db: Session, progress_callback=None, chunk_size: int = 50):
    """
    Fetches latest daily market data for all active symbols in parallel batches
    using yfinance multithreading, significantly speeding up synchronization.
    """
    symbols = repositories.get_active_symbols(db)
    if not symbols:
        return {"total": 0, "success": 0, "errors": 0}

    sym_map = {s.symbol: s.id for s in symbols}
    tickers = list(sym_map.keys())
    total = len(tickers)
    success = 0
    errors = 0

    chunks = [tickers[i:i + chunk_size] for i in range(0, total, chunk_size)]
    total_chunks = len(chunks)

    logger.info(f"Starting batch market data update for {total} symbols ({total_chunks} chunks)...")
    print(f"Starting batch market data update for {total} symbols ({total_chunks} chunks)...")

    processed = 0
    for chunk_idx, chunk in enumerate(chunks, 1):
        try:
            if progress_callback:
                pct = int((processed / total) * 100)
                progress_callback(processed, total, f"Batch {chunk_idx}/{total_chunks} ({pct}%)", "Downloading")

            # Batch download with internal multithreading
            data = yf.download(
                chunk,
                period="1y",
                interval="1d",
                group_by="ticker",
                threads=True,
                progress=False,
                auto_adjust=False
            )

            if data is None or not isinstance(data, pd.DataFrame) or data.empty:
                logger.warning(f"Batch {chunk_idx} returned empty, trying individual tickers...")
                for ticker in chunk:
                    processed += 1
                    s_id = sym_map.get(ticker)
                    if not s_id:
                        continue
                    try:
                        t = yf.Ticker(ticker)
                        sub_df = t.history(period="1y", interval="1d")
                        if sub_df is not None and not sub_df.empty:
                            sub_df = sub_df.dropna(how='all')
                            if not sub_df.empty:
                                if sub_df.index.tz is not None:
                                    sub_df.index = sub_df.index.tz_convert(TZ_JAKARTA)
                                else:
                                    sub_df.index = sub_df.index.tz_localize("UTC").tz_convert(TZ_JAKARTA)
                                repositories.save_daily_prices(db, s_id, sub_df)
                                success += 1
                            else:
                                errors += 1
                        else:
                            errors += 1
                    except Exception as ind_err:
                        errors += 1
                        logger.debug(f"Error fetching {ticker}: {ind_err}")
                continue

            for ticker in chunk:
                processed += 1
                s_id = sym_map.get(ticker)
                if not s_id:
                    continue

                try:
                    if len(chunk) == 1:
                        sub_df = data.copy()
                    else:
                        if hasattr(data.columns, 'levels') and ticker in data.columns.levels[0]:
                            sub_df = data[ticker].copy()
                        elif isinstance(data.columns, pd.MultiIndex) and ticker in data.columns:
                            sub_df = data[ticker].copy()
                        else:
                            errors += 1
                            continue

                    sub_df = sub_df.dropna(how='all')
                    if sub_df.empty:
                        continue

                    # Ensure timezone conversion to Asia/Jakarta
                    if sub_df.index.tz is not None:
                        sub_df.index = sub_df.index.tz_convert(TZ_JAKARTA)
                    else:
                        sub_df.index = sub_df.index.tz_localize("UTC").tz_convert(TZ_JAKARTA)

                    repositories.save_daily_prices(db, s_id, sub_df)
                    success += 1
                except Exception as row_err:
                    errors += 1
                    logger.debug(f"Error processing {ticker} from batch: {row_err}")

            logger.info(f"Chunk {chunk_idx}/{total_chunks} completed. Total saved: {success}/{processed}")

        except Exception as e:
            errors += len(chunk)
            logger.error(f"Error downloading chunk {chunk_idx}: {e}")
            print(f"Error downloading chunk {chunk_idx}: {e}")

    if progress_callback:
        progress_callback(total, total, "100%", "Complete")

    logger.info(f"Market data update finished. Success: {success}/{total}, Errors: {errors}")
    return {"total": total, "success": success, "errors": errors}
