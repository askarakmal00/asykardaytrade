"""
TradingView Market Data Provider
=================================
Menggunakan dua sumber data TradingView yang terbukti bekerja di VPS Tencent Cloud
(tidak kena rate-limit / 429 seperti Yahoo Finance):

1. TradingView Indonesia Scanner API  → real-time quote & bulk OHLCV hari ini
   Endpoint: https://scanner.tradingview.com/indonesia/scan
   Status VPS: 200 OK ✓ (diuji langsung di container)

2. tvdatafeed (WebSocket TradingView)  → data historis harian (500 candle ke belakang)
   Digunakan hanya untuk saham baru yang belum punya history di DB.

Format ticker konversi:
   DB / Yahoo Finance : BBCA.JK
   TradingView Scanner: BBCA  (IDX:BBCA)
   tvdatafeed         : symbol='BBCA', exchange='IDX'
"""

import requests
import datetime
import pytz
import logging
import pandas as pd
from typing import Dict, Any, List

from app.providers.base import MarketDataProvider

TZ_JAKARTA = pytz.timezone("Asia/Jakarta")
logger = logging.getLogger("provider.tradingview")

TV_SCANNER_URL = "https://scanner.tradingview.com/indonesia/scan"
_TV_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _to_idx_ticker(ticker_jk: str) -> str:
    """BBCA.JK  →  BBCA"""
    return ticker_jk.upper().replace(".JK", "").replace(".IDX", "")


def fetch_scanner_bulk_ohlcv(limit: int = 1000) -> Dict[str, Dict]:
    """
    Ambil OHLCV hari ini untuk SEMUA saham IDX dalam SATU request.
    Return: {'BBCA': {'open':..,'high':..,'low':..,'close':..,'volume':..}, ...}
    """
    payload = {
        "filter": [],
        "options": {"lang": "en"},
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": ["name", "open", "high", "low", "close", "volume"],
        "sort": {"sortBy": "volume", "sortOrder": "desc"},
        "range": [0, limit]
    }
    result: Dict[str, Dict] = {}
    try:
        r = requests.post(TV_SCANNER_URL, json=payload, headers=_TV_HEADERS, timeout=15)
        r.raise_for_status()
        for item in r.json().get("data", []):
            d = item.get("d", [])
            if len(d) < 6:
                continue
            name, op, hi, lo, cl, vol = d[0], d[1], d[2], d[3], d[4], d[5]
            # Hanya simpan jika semua OHLCV tersedia (bukan None)
            if name and cl is not None and op is not None:
                result[name] = {
                    "open":   float(op)  if op  is not None else float(cl),
                    "high":   float(hi)  if hi  is not None else float(cl),
                    "low":    float(lo)  if lo  is not None else float(cl),
                    "close":  float(cl),
                    "volume": float(vol) if vol is not None else 0.0,
                }
        logger.info(f"TradingView Scanner: {len(result)} saham berhasil dimuat")
    except Exception as e:
        logger.error(f"TradingView Scanner bulk fetch error: {e}")
    return result


def fetch_scanner_single_quote(ticker_jk: str) -> Dict[str, Any]:
    """
    Ambil quote real-time satu saham via TradingView Scanner.
    ticker_jk: 'BBCA.JK' format
    """
    idx_sym = _to_idx_ticker(ticker_jk)
    now_wib = datetime.datetime.now(TZ_JAKARTA)
    result: Dict[str, Any] = {
        "symbol":         ticker_jk,
        "current_price":  None,
        "previous_close": None,
        "day_open":       None,
        "day_high":       None,
        "day_low":        None,
        "volume":         None,
        "market_state":   "UNKNOWN",
        "data_source":    "TradingView Scanner",
        "data_note":      "Data dari TradingView Indonesia Scanner (near-realtime, bebas 429).",
        "quote_timestamp": now_wib.strftime("%Y-%m-%d %H:%M:%S WIB"),
    }
    try:
        payload = {
            "filter": [{"left": "name", "operation": "equal", "right": idx_sym}],
            "options": {"lang": "en"},
            "symbols": {"query": {"types": []}, "tickers": []},
            "columns": ["name", "open", "high", "low", "close", "volume", "change_abs"],
            "range": [0, 1]
        }
        r = requests.post(TV_SCANNER_URL, json=payload, headers=_TV_HEADERS, timeout=8)
        r.raise_for_status()
        data = r.json().get("data", [])
        if data:
            d = data[0]["d"]
            # d: [name, open, high, low, close, volume, change_abs]
            result["day_open"]       = d[1]
            result["day_high"]       = d[2]
            result["day_low"]        = d[3]
            result["current_price"]  = d[4]
            result["volume"]         = d[5]
            change_abs = d[6] if len(d) > 6 else None
            if result["current_price"] and change_abs is not None:
                result["previous_close"] = round(result["current_price"] - change_abs, 2)
    except Exception as e:
        logger.error(f"TradingView single quote error for {ticker_jk}: {e}")
    return result


def fetch_tvdatafeed_history(ticker_jk: str, n_bars: int = 500) -> pd.DataFrame:
    """
    Ambil data historis harian via tvdatafeed (TradingView WebSocket).
    ticker_jk: 'BBCA.JK' format
    Return: DataFrame dengan kolom Open, High, Low, Close, Volume + DatetimeIndex tz=Asia/Jakarta
    """
    try:
        from tvDatafeed import TvDatafeed, Interval  # type: ignore
        idx_sym = _to_idx_ticker(ticker_jk)
        tv = TvDatafeed()  # Tanpa login — data publik IDX tersedia
        df = tv.get_hist(
            symbol=idx_sym,
            exchange="IDX",
            interval=Interval.in_daily,
            n_bars=n_bars
        )
        if df is None or df.empty:
            logger.warning(f"tvdatafeed: tidak ada data untuk {ticker_jk}")
            return pd.DataFrame()

        # Rename lowercase → Title Case agar kompatibel dengan repositories.save_daily_prices
        df = df.rename(columns={
            "open":   "Open",
            "high":   "High",
            "low":    "Low",
            "close":  "Close",
            "volume": "Volume",
        })
        # Drop kolom 'symbol' jika ada (tvdatafeed kadang menyertakannya)
        df = df.drop(columns=["symbol"], errors="ignore")

        # Normalisasi timezone ke Asia/Jakarta
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC").tz_convert(TZ_JAKARTA)
        else:
            df.index = df.index.tz_convert(TZ_JAKARTA)

        df = df.dropna(subset=["Close"])
        logger.info(f"tvdatafeed {ticker_jk}: {len(df)} candle berhasil dimuat")
        return df
    except Exception as e:
        logger.error(f"tvdatafeed history error untuk {ticker_jk}: {e}")
        return pd.DataFrame()


class TradingViewProvider(MarketDataProvider):
    """
    Provider data pasar berbasis TradingView.
    - get_quote()        → TradingView Scanner (real-time, no 429)
    - get_daily_data()   → tvdatafeed WebSocket (500 candle historis)
    - get_intraday_data() → tvdatafeed WebSocket (intraday)
    """

    def get_symbols(self) -> List[str]:
        return []

    def get_daily_data(self, symbol: str, period: str = "1y") -> pd.DataFrame:
        n_bars = 500 if period in ("1y", "6mo") else 60
        return fetch_tvdatafeed_history(symbol, n_bars=n_bars)

    def get_intraday_data(
        self,
        symbol: str,
        interval: str = "15m",
        period: str = "5d"
    ) -> pd.DataFrame:
        try:
            from tvDatafeed import TvDatafeed, Interval  # type: ignore
            interval_map = {
                "1m":  Interval.in_1_minute,
                "3m":  Interval.in_3_minute,
                "5m":  Interval.in_5_minute,
                "15m": Interval.in_15_minute,
                "30m": Interval.in_30_minute,
                "1h":  Interval.in_1_hour,
                "2h":  Interval.in_2_hour,
                "4h":  Interval.in_4_hour,
            }
            tv_interval = interval_map.get(interval, Interval.in_15_minute)
            idx_sym = _to_idx_ticker(symbol)
            tv = TvDatafeed()
            df = tv.get_hist(
                symbol=idx_sym,
                exchange="IDX",
                interval=tv_interval,
                n_bars=300
            )
            if df is None or df.empty:
                return pd.DataFrame()
            df = df.rename(columns={
                "open": "Open", "high": "High",
                "low": "Low", "close": "Close", "volume": "Volume"
            })
            df = df.drop(columns=["symbol"], errors="ignore")
            if df.index.tz is None:
                df.index = df.index.tz_localize("UTC").tz_convert(TZ_JAKARTA)
            else:
                df.index = df.index.tz_convert(TZ_JAKARTA)
            return df.dropna(subset=["Close"])
        except Exception as e:
            logger.error(f"tvdatafeed intraday error untuk {symbol}: {e}")
            return pd.DataFrame()

    def get_quote(self, symbol: str) -> Dict[str, Any]:
        return fetch_scanner_single_quote(symbol)
