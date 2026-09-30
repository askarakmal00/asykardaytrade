import sys
sys.path.insert(0, 'D:/AsykarDayTrade')
import yfinance as yf
import pandas as pd
import datetime
import pytz

TZ = pytz.timezone('Asia/Jakarta')

ticker = yf.Ticker('MEDC.JK')
df = ticker.history(period='5d', interval='1d')
df.index = df.index.tz_convert(TZ)

print('=== RAW from yfinance ===')
print(df[['Open','High','Low','Close','Volume']].tail(5).to_string())
print()

# Simulate the NaN patch logic
last_row = df.iloc[-1]
last_ts = df.index[-1]
today_wib = datetime.datetime.now(TZ).date()
candle_date = last_ts.date()

ohlc_is_nan = pd.isna(last_row['Close']) and pd.isna(last_row['Open'])
is_recent = (candle_date == today_wib) or (candle_date == today_wib - datetime.timedelta(days=1))

print(f'Last candle date : {candle_date}')
print(f'Today WIB        : {today_wib}')
print(f'OHLC is NaN      : {ohlc_is_nan}')
print(f'Is recent        : {is_recent}')

if ohlc_is_nan and is_recent:
    fi = ticker.fast_info
    last_price = getattr(fi, 'last_price', None)
    day_open   = getattr(fi, 'open', None)
    day_high   = getattr(fi, 'day_high', None)
    day_low    = getattr(fi, 'day_low', None)
    volume     = getattr(fi, 'last_volume', None)
    
    print(f'\nPatching NaN candle with fast_info:')
    print(f'  last_price = {last_price}')
    print(f'  day_open   = {day_open}')
    print(f'  day_high   = {day_high}')
    print(f'  day_low    = {day_low}')
    print(f'  volume     = {volume}')
    
    if last_price and last_price > 0:
        df.at[last_ts, 'Open']   = day_open or last_price
        df.at[last_ts, 'High']   = day_high or last_price
        df.at[last_ts, 'Low']    = day_low  or last_price
        df.at[last_ts, 'Close']  = last_price
        df.at[last_ts, 'Volume'] = volume or 0
        print('\n=== AFTER PATCH ===')
        print(df[['Open','High','Low','Close','Volume']].tail(3).to_string())
        print('\nLatest Daily Close: Rp', format(df['Close'].iloc[-1], ',.0f'))
    else:
        print('Patch failed - fast_info last_price unavailable')
else:
    print(f'\nNo patch needed. Latest Close: Rp {df["Close"].iloc[-1]:,.0f}')
