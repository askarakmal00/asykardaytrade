"""
Market Data Audit Script for MEDC.JK
Run from project root: python scripts/audit_market_data.py
"""
import yfinance as yf
import pandas as pd
import datetime
import pytz

SYMBOL = "MEDC.JK"
TZ_JAKARTA = pytz.timezone("Asia/Jakarta")

def ts_to_jakarta(ts):
    if ts is None:
        return "N/A"
    if hasattr(ts, 'tzinfo') and ts.tzinfo is not None:
        return ts.astimezone(TZ_JAKARTA).strftime("%Y-%m-%d %H:%M:%S %Z")
    # naive UTC
    return pytz.utc.localize(ts).astimezone(TZ_JAKARTA).strftime("%Y-%m-%d %H:%M:%S %Z")

print("=" * 70)
print(f"  MARKET DATA AUDIT: {SYMBOL}")
print(f"  System Time (UTC)   : {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
print(f"  System Time (WIB)   : {datetime.datetime.now(TZ_JAKARTA).strftime('%Y-%m-%d %H:%M:%S %Z')}")
print("=" * 70)

ticker = yf.Ticker(SYMBOL)

# ─────────────────────────────────────────────────────────────────────────────
# A. FAST_INFO / QUOTE (real-time or near-realtime price)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[A] FAST_INFO (Quote / Real-time snapshot)")
print("-" * 50)
try:
    fi = ticker.fast_info
    for attr in [
        "last_price",
        "previous_close",
        "open",
        "day_high",
        "day_low",
        "last_volume",
        "regular_market_previous_close",
    ]:
        val = getattr(fi, attr, "N/A")
        print(f"  {attr:<40} : {val}")
except Exception as e:
    print(f"  fast_info error: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# B. INFO / MARKET STATE
# ─────────────────────────────────────────────────────────────────────────────
print("\n[B] INFO (selected fields)")
print("-" * 50)
try:
    info = ticker.info
    fields = [
        "regularMarketPrice",
        "regularMarketPreviousClose",
        "regularMarketOpen",
        "regularMarketDayHigh",
        "regularMarketDayLow",
        "regularMarketVolume",
        "regularMarketTime",
        "preMarketPrice",
        "postMarketPrice",
        "marketState",
        "exchangeTimezoneShortName",
        "currency",
    ]
    for f in fields:
        val = info.get(f, "N/A")
        if f == "regularMarketTime" and val != "N/A":
            # regularMarketTime is a POSIX timestamp
            dt = datetime.datetime.fromtimestamp(val, tz=pytz.utc)
            val = f"{val}  →  {dt.astimezone(TZ_JAKARTA).strftime('%Y-%m-%d %H:%M:%S %Z')}"
        print(f"  {f:<40} : {val}")
except Exception as e:
    print(f"  ticker.info error: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# C. DAILY DATA  (1d)  — last 5 candles
# ─────────────────────────────────────────────────────────────────────────────
print("\n[C] DAILY OHLCV (interval=1d, period=10d) — last 5 rows")
print("-" * 50)
try:
    daily = ticker.history(period="10d", interval="1d")
    if daily.empty:
        print("  No daily data returned.")
    else:
        print(f"  Index timezone: {daily.index.tz}")
        print(f"  Total rows    : {len(daily)}")
        print()
        tail5 = daily.tail(5).copy()
        tail5.index = tail5.index.map(ts_to_jakarta)
        print(tail5[["Open", "High", "Low", "Close", "Volume"]].to_string())
        last_daily_ts = daily.index[-1]
        last_daily_close = daily["Close"].iloc[-1]
        print(f"\n  Latest candle timestamp (raw): {last_daily_ts}")
        print(f"  Latest candle timestamp (WIB): {ts_to_jakarta(last_daily_ts)}")
        print(f"  Latest Daily Close           : {last_daily_close:,.2f}")
        # Is the candle complete? Daily candle is complete if date < today (WIB)
        today_wib = datetime.datetime.now(TZ_JAKARTA).date()
        if hasattr(last_daily_ts, 'date'):
            candle_date = last_daily_ts.date()
        else:
            candle_date = last_daily_ts.to_pydatetime().date()
        is_complete = candle_date < today_wib
        print(f"  Today (WIB)                  : {today_wib}")
        print(f"  Candle date                  : {candle_date}")
        print(f"  Candle complete?             : {'YES — historical' if is_complete else 'POSSIBLY FORMING — same-day candle'}")
except Exception as e:
    print(f"  Daily data error: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# D. 1H DATA — last 5 candles
# ─────────────────────────────────────────────────────────────────────────────
print("\n[D] INTRADAY 1H (interval=1h, period=5d) — last 5 rows")
print("-" * 50)
try:
    hourly = ticker.history(period="5d", interval="1h")
    if hourly.empty:
        print("  No 1H data returned.")
    else:
        print(f"  Index timezone: {hourly.index.tz}")
        print(f"  Total rows    : {len(hourly)}")
        print()
        tail5 = hourly.tail(5).copy()
        tail5.index = tail5.index.map(ts_to_jakarta)
        print(tail5[["Open", "High", "Low", "Close", "Volume"]].to_string())
        last_1h_ts = hourly.index[-1]
        last_1h_close = hourly["Close"].iloc[-1]
        print(f"\n  Latest 1H candle timestamp (raw): {last_1h_ts}")
        print(f"  Latest 1H candle timestamp (WIB): {ts_to_jakarta(last_1h_ts)}")
        print(f"  Latest 1H Close                 : {last_1h_close:,.2f}")
        now_wib = datetime.datetime.now(TZ_JAKARTA)
        last_1h_ts_aware = last_1h_ts.astimezone(TZ_JAKARTA)
        delta_minutes = (now_wib - last_1h_ts_aware.replace(tzinfo=TZ_JAKARTA)).total_seconds() / 60
        print(f"  Minutes since last 1H candle    : {delta_minutes:.1f} min")
        print(f"  Candle complete?                : {'Likely complete' if delta_minutes > 65 else 'Possibly still forming'}")
except Exception as e:
    print(f"  1H data error: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# E. 15M DATA — last 5 candles
# ─────────────────────────────────────────────────────────────────────────────
print("\n[E] INTRADAY 15M (interval=15m, period=5d) — last 5 rows")
print("-" * 50)
try:
    m15 = ticker.history(period="5d", interval="15m")
    if m15.empty:
        print("  No 15M data returned.")
    else:
        print(f"  Index timezone: {m15.index.tz}")
        print(f"  Total rows    : {len(m15)}")
        print()
        tail5 = m15.tail(5).copy()
        tail5.index = tail5.index.map(ts_to_jakarta)
        print(tail5[["Open", "High", "Low", "Close", "Volume"]].to_string())
        last_15m_ts = m15.index[-1]
        last_15m_close = m15["Close"].iloc[-1]
        print(f"\n  Latest 15M candle timestamp (raw): {last_15m_ts}")
        print(f"  Latest 15M candle timestamp (WIB): {ts_to_jakarta(last_15m_ts)}")
        print(f"  Latest 15M Close                 : {last_15m_close:,.2f}")
        now_wib = datetime.datetime.now(TZ_JAKARTA)
        last_15m_ts_aware = last_15m_ts.astimezone(TZ_JAKARTA)
        delta_minutes = (now_wib - last_15m_ts_aware).total_seconds() / 60
        print(f"  Minutes since last 15M candle    : {delta_minutes:.1f} min")
        print(f"  Candle complete?                 : {'Likely complete' if delta_minutes > 20 else 'Possibly still forming'}")
except Exception as e:
    print(f"  15M data error: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# F. DISCREPANCY SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("  DISCREPANCY ANALYSIS SUMMARY")
print("=" * 70)
try:
    last_price = ticker.fast_info.last_price
    prev_close = ticker.fast_info.previous_close
    daily_last = yf.Ticker(SYMBOL).history(period="5d", interval="1d")
    daily_close = daily_last["Close"].iloc[-1] if not daily_last.empty else None
    
    print(f"  fast_info.last_price        : {last_price:,.2f}  ← This is closest to realtime" if last_price else "  fast_info.last_price        : N/A")
    print(f"  fast_info.previous_close    : {prev_close:,.2f}" if prev_close else "  fast_info.previous_close    : N/A")
    print(f"  Daily OHLCV Close (iloc[-1]): {daily_close:,.2f}  ← This is what the app currently displays" if daily_close else "  Daily OHLCV Close           : N/A")
    
    if last_price and daily_close:
        diff = last_price - daily_close
        diff_pct = (diff / daily_close) * 100
        print(f"\n  Difference                  : {diff:+,.2f} ({diff_pct:+.2f}%)")
        print(f"\n  EXPLANATION:")
        if abs(diff) > 10:
            print(f"  The app shows daily_ohlcv['Close'].iloc[-1] = {daily_close:,.2f}")
            print(f"  This is the PREVIOUS SESSION CLOSE, not today's price.")
            print(f"  The true latest price (fast_info.last_price) = {last_price:,.2f}")
            print(f"  TradingView shows the live quote or latest intraday close.")
            print(f"  The fix: use fast_info.last_price for 'Current Price' display,")
            print(f"  and clearly label the daily candle close as 'Daily Close (prev session)'")
        else:
            print(f"  Small difference — may be normal data delay from Yahoo Finance.")

except Exception as e:
    print(f"  Summary error: {e}")

print("=" * 70)
