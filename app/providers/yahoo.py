import yfinance as yf
import pandas as pd
import datetime
import pytz
import logging
from typing import List, Dict, Any

from app.providers.base import MarketDataProvider

TZ_JAKARTA = pytz.timezone("Asia/Jakarta")
logger = logging.getLogger("provider.yahoo")


def _to_jakarta_str(ts) -> str:
    """Convert any timestamp to Asia/Jakarta string for display."""
    if ts is None:
        return "N/A"
    try:
        if hasattr(ts, 'tzinfo') and ts.tzinfo is not None:
            return ts.astimezone(TZ_JAKARTA).strftime("%Y-%m-%d %H:%M:%S WIB")
        # Assume naive UTC
        return pytz.utc.localize(ts).astimezone(TZ_JAKARTA).strftime("%Y-%m-%d %H:%M:%S WIB")
    except Exception:
        return str(ts)


class YahooFinanceProvider(MarketDataProvider):

    def get_symbols(self) -> List[str]:
        # IDX symbols are managed via idx_symbols.csv / DB — not from yfinance
        return []

    # ─────────────────────────────────────────────────────────────────────────
    # DAILY OHLCV
    # Returns completed daily candles.
    # IMPORTANT: Do NOT use Close[-1] as "Current Price".
    #            Label it "Daily Close" — it is the PREVIOUS SESSION close.
    # ─────────────────────────────────────────────────────────────────────────
    # DAILY OHLCV
    # Returns completed daily candles with today's session patched from fast_info
    # if Yahoo Finance hasn't finalized the candle yet (NaN row bug).
    # ─────────────────────────────────────────────────────────────────────────
    def get_daily_data(self, symbol: str, period: str = "1y") -> pd.DataFrame:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval="1d")
            if df.empty:
                logger.warning(f"No daily data for {symbol}")
                return pd.DataFrame()

            # Normalize timezone to Asia/Jakarta
            if df.index.tz is not None:
                df.index = df.index.tz_convert(TZ_JAKARTA)
            else:
                df.index = df.index.tz_localize("UTC").tz_convert(TZ_JAKARTA)

            # ── Handle NaN candle for today's session ────────────────────────
            # Yahoo Finance sometimes returns today's candle as NaN OHLC even
            # after market close. We patch it using fast_info (last known data).
            if not df.empty:
                last_row = df.iloc[-1]
                last_ts = df.index[-1]
                today_wib = datetime.datetime.now(TZ_JAKARTA).date()
                candle_date = last_ts.date()

                is_today = (candle_date == today_wib) or (candle_date == today_wib - datetime.timedelta(days=1))
                ohlc_is_nan = pd.isna(last_row["Close"]) and pd.isna(last_row["Open"])

                if ohlc_is_nan and is_today:
                    # Try to patch from fast_info
                    try:
                        fi = ticker.fast_info
                        last_price = getattr(fi, "last_price", None)
                        day_open   = getattr(fi, "open", None)
                        day_high   = getattr(fi, "day_high", None)
                        day_low    = getattr(fi, "day_low", None)
                        volume     = getattr(fi, "last_volume", None)

                        if last_price and last_price > 0:
                            df.at[last_ts, "Open"]   = day_open  or last_price
                            df.at[last_ts, "High"]   = day_high  or last_price
                            df.at[last_ts, "Low"]    = day_low   or last_price
                            df.at[last_ts, "Close"]  = last_price
                            df.at[last_ts, "Volume"] = volume or 0
                            logger.info(f"{symbol}: Patched NaN daily candle with fast_info (close={last_price})")
                        else:
                            # fast_info also unavailable — drop the NaN row
                            logger.debug(f"{symbol}: Dropping NaN daily row (fast_info unavailable)")
                            df = df.iloc[:-1]
                    except Exception as patch_err:
                        logger.debug(f"{symbol}: NaN patch failed: {patch_err}, dropping row")
                        df = df.iloc[:-1]

            # Tag with metadata
            df.attrs["symbol"]      = symbol
            df.attrs["interval"]    = "1d"
            df.attrs["data_source"] = "Yahoo Finance"
            df.attrs["data_note"]   = "Daily Close from completed session. NaN rows patched from fast_info."

            return df
        except Exception as e:
            logger.error(f"Error fetching daily data for {symbol}: {e}")
            return pd.DataFrame()

    # ─────────────────────────────────────────────────────────────────────────
    # INTRADAY OHLCV
    # Returns intraday candles at the specified interval.
    # The last row close is labeled "Latest {interval} Close" — not Current Price.
    # ─────────────────────────────────────────────────────────────────────────
    def get_intraday_data(
        self,
        symbol: str,
        interval: str = "15m",
        period: str = "5d"
    ) -> pd.DataFrame:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            if df.empty:
                logger.info(f"No {interval} intraday data for {symbol}")
                return pd.DataFrame()

            if df.index.tz is not None:
                df.index = df.index.tz_convert(TZ_JAKARTA)
            else:
                df.index = df.index.tz_localize("UTC").tz_convert(TZ_JAKARTA)

            df.attrs["symbol"] = symbol
            df.attrs["interval"] = interval
            df.attrs["data_source"] = "Yahoo Finance"
            df.attrs["data_note"] = f"Intraday {interval} candles. Last candle may still be forming."

            return df
        except Exception as e:
            logger.error(f"Error fetching {interval} intraday data for {symbol}: {e}")
            return pd.DataFrame()

    # ─────────────────────────────────────────────────────────────────────────
    # QUOTE — Real-time or near-real-time price snapshot
    # This is the ONLY correct source for "Current Price".
    # ─────────────────────────────────────────────────────────────────────────
    def get_quote(self, symbol: str) -> Dict[str, Any]:
        now_wib = datetime.datetime.now(TZ_JAKARTA)
        result = {
            "symbol": symbol,
            "current_price": None,
            "previous_close": None,
            "day_open": None,
            "day_high": None,
            "day_low": None,
            "volume": None,
            "market_state": "UNKNOWN",
            "data_source": "Yahoo Finance",
            "data_note": "Yahoo Finance provides delayed data (typically 15-20 min). Not guaranteed real-time.",
            "quote_timestamp": now_wib.strftime("%Y-%m-%d %H:%M:%S WIB"),
        }
        try:
            ticker = yf.Ticker(symbol)
            fi = ticker.fast_info

            result["current_price"] = getattr(fi, "last_price", None)
            result["previous_close"] = getattr(fi, "previous_close", None)
            result["day_open"] = getattr(fi, "open", None)
            result["day_high"] = getattr(fi, "day_high", None)
            result["day_low"] = getattr(fi, "day_low", None)
            result["volume"] = getattr(fi, "last_volume", None)

        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")

        return result
