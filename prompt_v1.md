# IDX DAY TRADE SIGNAL SYSTEM — LOCAL FIRST

## 1. PROJECT OBJECTIVE

Bangun aplikasi lokal untuk melakukan:

1. Download market data saham Indonesia.
2. Menyimpan data market secara lokal.
3. Menghitung technical indicators.
4. Melakukan screening saham IDX.
5. Memberikan ranking kandidat day trade.
6. Mendeteksi setup pullback dan breakout.
7. Menghasilkan Entry, Stop Loss, TP1, TP2, dan Risk/Reward.
8. Melakukan backtesting strategi.

Prioritas project saat ini:

> **FUNCTIONALITY FIRST.**

Aplikasi harus dapat berjalan sepenuhnya di komputer lokal.

Jangan implementasikan deployment/cloud terlebih dahulu.

Jangan gunakan:

* AI / LLM
* Supabase
* PostgreSQL
* Docker
* Redis
* microservices
* authentication
* paid market data API
* leverage
* automatic trading / broker execution

Gunakan solusi sesederhana mungkin selama fungsinya berjalan dengan benar.

---

# 2. CORE PRINCIPLE

Arsitektur utama:

```text
Yahoo Finance
      ↓
Market Data Provider
      ↓
SQLite
      ↓
Indicator Engine
      ↓
Stock Screener
      ↓
Ranking Engine
      ↓
Signal Engine
      ↓
Local Dashboard
      ↓
Backtesting
```

Semua signal harus **rule-based**.

Tidak menggunakan AI untuk menentukan BUY/SELL.

---

# 3. TECHNOLOGY STACK

Gunakan:

### Backend

```text
Python
FastAPI
```

### Data Processing

```text
pandas
numpy
yfinance
ta
```

### Database

```text
SQLite
```

Database file:

```text
data/stock_signal.db
```

### ORM

Gunakan:

```text
SQLAlchemy
```

### Frontend

Untuk versi lokal pertama gunakan solusi sederhana.

Prioritas:

```text
FastAPI + Jinja2 + Bootstrap
```

atau HTML/CSS/JavaScript sederhana.

Jangan menggunakan Next.js/React terlebih dahulu jika hanya menambah kompleksitas.

### Chart

Gunakan library JavaScript gratis yang dapat menampilkan candlestick.

Prefer:

```text
TradingView Lightweight Charts
```

Jika implementasinya menyulitkan, gunakan library chart sederhana terlebih dahulu.

---

# 4. RUNNING THE APPLICATION

Target akhir:

User cukup menjalankan:

```bash
python run.py
```

Kemudian aplikasi tersedia di:

```text
http://localhost:8000
```

Jika database belum tersedia:

* buat database otomatis
* buat table otomatis

Jika market data belum tersedia:

* tampilkan tombol Update Market Data

Jangan membuat setup awal yang rumit.

---

# 5. PROJECT STRUCTURE

Gunakan struktur:

```text
idx-signal/
│
├── app/
│   ├── main.py
│   │
│   ├── config.py
│   │
│   ├── database/
│   │   ├── connection.py
│   │   ├── models.py
│   │   └── repositories.py
│   │
│   ├── providers/
│   │   ├── base.py
│   │   └── yahoo.py
│   │
│   ├── indicators/
│   │   ├── trend.py
│   │   ├── momentum.py
│   │   └── volume.py
│   │
│   ├── scanner/
│   │   ├── screener.py
│   │   └── ranking.py
│   │
│   ├── strategy/
│   │   ├── pullback.py
│   │   ├── breakout.py
│   │   └── signal_engine.py
│   │
│   ├── backtest/
│   │   ├── engine.py
│   │   └── metrics.py
│   │
│   ├── services/
│   │   ├── market_data.py
│   │   └── scanner_service.py
│   │
│   ├── templates/
│   │
│   └── static/
│
├── data/
│   └── stock_signal.db
│
├── tests/
│
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
└── run.py
```

Keep the architecture modular but simple.

Do not over-engineer.

---

# 6. FREE MARKET DATA

Gunakan:

```text
Yahoo Finance
```

melalui:

```text
yfinance
```

Contoh IDX ticker:

```text
BBCA.JK
BBRI.JK
BMRI.JK
TLKM.JK
BRMS.JK
HRUM.JK
```

Semua harga dan market data harus berasal dari provider.

Jangan hardcode harga saham.

Jangan fabricate market data.

---

# 7. MARKET DATA PROVIDER

Buat interface sederhana:

```python
class MarketDataProvider:

    def get_symbols(self):
        pass

    def get_daily_data(self, symbol, period="1y"):
        pass

    def get_intraday_data(
        self,
        symbol,
        interval="15m",
        period="5d"
    ):
        pass
```

Implementasi pertama:

```text
YahooFinanceProvider
```

Tujuannya supaya provider bisa diganti di masa depan tanpa mengubah signal engine.

---

# 8. DATA SOURCE STATUS

Karena Yahoo Finance gratis:

Jangan mengklaim data sebagai guaranteed realtime.

Dashboard harus menampilkan:

```text
Data Source:
Yahoo Finance

Last Update:
YYYY-MM-DD HH:MM

Data Status:
Delayed / Historical
```

Jika data tidak tersedia:

```text
DATA_UNAVAILABLE
```

Jangan mengarang data pengganti.

---

# 9. IDX STOCK UNIVERSE

Aplikasi membutuhkan daftar ticker saham Indonesia.

Buat:

```text
data/idx_symbols.csv
```

Format:

```text
symbol,name
BBCA.JK,Bank Central Asia
BBRI.JK,Bank Rakyat Indonesia
...
```

Buat mechanism untuk update symbol list di masa depan.

Untuk development awal, boleh gunakan cached/local IDX ticker list.

Jangan membuat aplikasi gagal total hanya karena symbol source sedang tidak tersedia.

---

# 10. SQLITE DATABASE

Gunakan SQLite.

File:

```text
data/stock_signal.db
```

Database tidak perlu dioptimasi berlebihan untuk versi pertama.

---

# 11. TABLE: SYMBOLS

Fields:

```text
id
symbol
name
sector
is_active
created_at
updated_at
```

---

# 12. TABLE: DAILY_PRICES

Fields:

```text
id
symbol_id
date
open
high
low
close
volume
created_at
```

Unique:

```text
symbol_id + date
```

---

# 13. TABLE: INTRADAY_PRICES

Fields:

```text
id
symbol_id
timestamp
interval
open
high
low
close
volume
created_at
```

Unique:

```text
symbol_id + timestamp + interval
```

Jangan menyimpan duplicate candles.

---

# 14. TABLE: SIGNALS

Fields:

```text
id
symbol_id
timestamp

price

score
grade

setup
status

entry_low
entry_high

stop_loss

tp1
tp2

risk_reward

reason

data_timestamp

created_at
```

---

# 15. MARKET DATA UPDATE

Dashboard harus memiliki tombol:

```text
UPDATE MARKET DATA
```

Ketika ditekan:

1. Ambil daftar active symbols.
2. Download OHLCV.
3. Validate data.
4. Save/update SQLite.
5. Calculate latest indicators.
6. Run screener.
7. Generate ranking.
8. Generate signals.

Tampilkan progress.

Contoh:

```text
Downloading:

BBCA  ✓
BBRI  ✓
BMRI  ✓
BRMS  ✓
HRUM  ✓

187 / 900 stocks
```

Jangan membuat UI freeze tanpa informasi progress.

---

# 16. DOWNLOAD STRATEGY

Jangan selalu download seluruh historical data.

Jika database kosong:

```text
Initial Download
```

download historical daily data.

Jika database sudah memiliki data:

```text
Incremental Update
```

download hanya data terbaru yang diperlukan.

Tujuannya mempercepat scanner.

---

# 17. DAILY OHLCV

Minimal simpan:

```text
Date
Open
High
Low
Close
Volume
```

Jangan mencampur adjusted price tanpa aturan.

Gunakan consistent price basis.

---

# 18. INTRADAY DATA

Jika tersedia dari Yahoo:

Gunakan:

```text
1h
15m
5m
```

Tetapi pahami bahwa Yahoo memiliki limitation untuk historical intraday.

Jika tidak tersedia:

```text
DATA_UNAVAILABLE
```

Signal engine tidak boleh membuat data sendiri.

---

# 19. TECHNICAL INDICATORS

Hitung:

### TREND

```text
EMA9
EMA21
MA20
MA50
```

### MOMENTUM

```text
RSI14
Stochastic RSI
```

### VOLUME

```text
Volume
Volume MA20
Volume Ratio
Volume Change
```

### INTRADAY

Jika memungkinkan:

```text
VWAP
```

---

# 20. BASE STOCK SCREENER

Buat screener yang meniru logic yang sudah digunakan secara manual.

Default:

```text
Price > 200
```

```text
RSI14 > 50
```

```text
RSI14 < 70
```

```text
Volume > 1,000,000
```

Estimated Value:

```text
Close × Volume
```

Filter:

```text
Estimated Value > 10,000,000,000
```

Volume momentum:

```text
Volume > Volume MA20
```

Prefer:

```text
Volume / Volume MA20 >= 1.5
```

Semua parameter harus configurable.

---

# 21. CONFIGURATION

Buat:

```text
app/config.py
```

Default:

```python
MIN_PRICE = 200

RSI_MIN = 50
RSI_MAX = 70

MIN_VOLUME = 1_000_000
MIN_VALUE = 10_000_000_000

MIN_VOLUME_RATIO = 1.5

EMA_FAST = 9
EMA_SLOW = 21

MIN_SIGNAL_SCORE = 75

MIN_RISK_REWARD = 1.5
```

Jangan menyebarkan magic numbers di source code.

---

# 22. SCREENER OUTPUT

Dashboard harus memiliki halaman:

```text
/screener
```

Tampilkan:

| Rank | Symbol | Price | Change | RSI | Volume Ratio | Value | Score |
| ---- | ------ | ----- | ------ | --- | ------------ | ----- | ----- |

Default sort:

```text
Score DESC
```

---

# 23. CANDIDATE LIMIT

Jangan tampilkan ratusan saham sebagai rekomendasi utama.

Tampilkan:

```text
TOP 10 CANDIDATES
```

Tetapi user tetap dapat membuka:

```text
VIEW ALL
```

---

# 24. TREND ANALYSIS

Untuk kandidat hasil screener:

Analisis:

```text
1H
```

Jika tersedia.

Bullish:

```text
Price > EMA9
AND
EMA9 > EMA21
```

Tambahan:

```text
EMA21 slope > 0
```

Jika 1H tidak tersedia:

gunakan daily context tetapi tandai:

```text
INTRADAY_DATA_UNAVAILABLE
```

---

# 25. DAILY CONTEXT

Daily bullish:

```text
Close > MA20
AND
MA20 > MA50
```

Daily neutral:

trend tidak jelas.

Daily bearish:

```text
Close < MA20
AND
MA20 < MA50
```

Daily hanya menjadi context.

Bukan BUY trigger.

---

# 26. PULLBACK SETUP

Setup utama pertama:

```text
PULLBACK
```

Syarat dasar:

```text
1H bullish
AND
price pulls back toward EMA9 / EMA21
AND
support remains valid
AND
momentum begins recovering
```

Prefer:

```text
15M reversal confirmation
```

Status:

```text
WAIT_PULLBACK
```

Jika confirmation:

```text
READY
```

---

# 27. BREAKOUT SETUP

Setup kedua:

```text
BREAKOUT
```

Syarat:

```text
1H bullish
AND
price near resistance
AND
consolidation exists
AND
breakout occurs
AND
volume expands
```

Prefer:

```text
BREAKOUT
→ RETEST
→ HOLD
```

Baru:

```text
READY
```

Jangan membeli hanya karena satu candle hijau besar.

---

# 28. EXTENDED PRICE PROTECTION

Ini wajib.

Hitung:

```text
Distance From EMA9 %
```

Formula:

```text
(price - EMA9) / EMA9 × 100
```

Jika:

```text
> 3%
```

beri penalty.

Jika:

```text
> 5%
```

status:

```text
WAIT_PULLBACK
```

meskipun score tinggi.

Tujuannya menghindari FOMO.

---

# 29. RSI PROTECTION

Jika:

```text
RSI > 70
```

beri warning:

```text
OVERBOUGHT
```

Jika:

```text
RSI > 75
```

beri score penalty.

Jangan otomatis BUY saham hanya karena momentum tinggi.

---

# 30. SUPPORT / RESISTANCE

Hitung:

```text
Recent Swing High
Recent Swing Low
Previous High
Previous Low
EMA9
EMA21
MA20
```

Gunakan area:

```text
Support Zone
Resistance Zone
```

Bukan hanya satu angka.

---

# 31. ENTRY ENGINE

Entry harus berdasarkan setup.

Contoh:

```text
Entry Zone:
880–885
```

bukan:

```text
BUY NOW AT 890
```

Jika harga berada di atas entry zone:

```text
WAIT_PULLBACK
```

Jika harga sudah terlalu jauh:

```text
SKIP
```

---

# 32. STOP LOSS ENGINE

Stop loss berdasarkan:

```text
recent swing low
support invalidation
ATR if available
```

Jangan selalu menggunakan fixed -2%.

Contoh:

```text
Support:
875

Entry:
885

Stop:
870
```

---

# 33. TAKE PROFIT ENGINE

Generate:

```text
TP1
TP2
```

berdasarkan:

* resistance
* previous high
* risk/reward

Minimum:

```text
RR >= 1.5
```

Prefer:

```text
RR >= 2
```

Jika RR tidak memenuhi:

```text
NO_TRADE
```

---

# 34. SIGNAL SCORING

Score:

```text
0–100
```

### TREND — 25

```text
Price > EMA9        +8
EMA9 > EMA21        +8
EMA21 rising        +5
Daily bullish       +4
```

### MOMENTUM — 20

```text
RSI 50–70           +10
Positive momentum   +5
Stoch RSI reversal  +5
```

### LIQUIDITY — 20

```text
Value > 10B         +7
Volume > 1M         +5
Volume ratio > 1.5  +8
```

### SETUP — 25

```text
Valid pullback      +15
Support reaction    +5
Confirmation        +5
```

atau:

```text
Valid breakout      +15
Volume breakout     +5
Successful retest   +5
```

### RISK/REWARD — 10

```text
RR >= 1.5           +5
RR >= 2             +10
```

Gunakan nilai tertinggi yang applicable, bukan keduanya sekaligus.

---

# 35. SCORE PENALTY

Tambahkan penalty:

```text
RSI > 75              -10

Distance EMA9 > 3%    -10

Distance EMA9 > 5%    -20

Low liquidity         -20
```

Score akhir:

```text
0 <= Score <= 100
```

---

# 36. SIGNAL CLASSIFICATION

```text
85–100 = A+
75–84  = A
65–74  = WATCH
50–64  = LOW QUALITY
<50    = NO TRADE
```

Tetapi score tinggi tidak otomatis BUY.

BUY/READY tetap membutuhkan valid setup.

---

# 37. SIGNAL STATUS

Gunakan:

```text
WATCH
WAIT_PULLBACK
WAIT_BREAKOUT
READY
NO_TRADE
SKIP
DATA_UNAVAILABLE
STALE_DATA
```

Untuk tahap lokal pertama:

Jangan implementasikan automatic broker BUY.

`READY` hanya berarti setup memenuhi rule.

---

# 38. SIGNAL OUTPUT

Contoh:

```text
BRMS

Price:
650

Score:
82

Grade:
A

Trend:
BULLISH

Setup:
PULLBACK

RSI:
63

EMA9:
637

EMA21:
628

Support:
635–640

Resistance:
660–670

Entry:
638–642

Stop Loss:
630

TP1:
660

TP2:
670

Risk/Reward:
1:2.1

Status:
WAIT_PULLBACK
```

Semua angka harus dihitung dari data.

Jangan hardcode contoh tersebut.

---

# 39. RULE-BASED EXPLANATION

Tanpa AI.

Generate explanation dari rule.

Contoh:

```text
WHY THIS STOCK?

✓ Price above EMA9
✓ EMA9 above EMA21
✓ RSI bullish but not overbought
✓ Volume above 20-day average
✓ Estimated transaction value > Rp10B
✓ Trend bullish

WHY NOT READY?

✗ Price is 3.8% above EMA9
✗ Waiting for pullback
```

Gunakan template.

---

# 40. DASHBOARD HOME

Route:

```text
/
```

Tampilkan:

### Header

```text
IDX DAY TRADE SIGNAL
```

### Data Status

```text
Yahoo Finance
Last Update
Number of Stocks Scanned
```

### Summary

```text
Stocks Scanned
Passed Screener
A+ Setup
A Setup
Watch
```

### Top Candidates

Tampilkan maksimal 10.

---

# 41. CANDIDATE DETAIL

Route:

```text
/stock/{symbol}
```

Tampilkan:

* candlestick
* EMA9
* EMA21
* volume
* RSI
* support
* resistance
* score
* setup
* entry
* SL
* TP1
* TP2
* RR
* explanation

---

# 42. MANUAL REFRESH

Tambahkan button:

```text
REFRESH DATA
```

dan:

```text
RUN SCREENER
```

Untuk versi pertama:

**manual refresh lebih penting daripada scheduler.**

Jangan implementasikan scheduler sebelum manual process stabil.

---

# 43. SCAN HISTORY

Simpan setiap scan:

```text
scan_runs
```

Fields:

```text
id
started_at
completed_at
symbols_scanned
symbols_passed
status
error_count
```

Tujuannya agar kita tahu apakah scan berhasil.

---

# 44. ERROR HANDLING

Jika satu ticker gagal:

```text
ERROR HRUM.JK
```

jangan hentikan seluruh scan.

Continue ke ticker berikutnya.

Simpan error log.

---

# 45. LOGGING

Buat:

```text
logs/app.log
```

Log:

```text
market data update
ticker failure
scanner start
scanner finish
signal generation
database error
```

---

# 46. PERFORMANCE

Jangan download ticker satu per satu secara sangat lambat jika yfinance mendukung batch download.

Gunakan batch bila stabil.

Tetapi prioritaskan:

```text
correctness > speed
```

Implementasikan retry dengan batas yang masuk akal.

---

# 47. BACKTESTING — PHASE 3

Setelah scanner + signal stabil, buat:

```text
/backtest
```

User dapat memilih:

```text
Start Date
End Date
Setup
```

Kemudian:

```text
RUN BACKTEST
```

---

# 48. BACKTEST RULE

Backtest WAJIB menggunakan strategy code yang sama dengan signal engine.

Jangan duplicate logic.

Contoh:

```python
strategy.evaluate(data)
```

digunakan oleh:

```text
Live Scanner
```

dan:

```text
Backtester
```

---

# 49. NO LOOK-AHEAD BIAS

Sangat penting.

Pada candle timestamp T:

hanya boleh menggunakan data:

```text
<= T
```

Tidak boleh menggunakan:

```text
T+1
future high
future low
future volume
```

untuk menentukan signal pada T.

---

# 50. BACKTEST METRICS

Tampilkan:

```text
Total Trades
Wins
Losses
Win Rate
Average Win
Average Loss
Profit Factor
Expectancy
Average R
Max Drawdown
```

---

# 51. PERFORMANCE BY SETUP

Pisahkan:

```text
PULLBACK
BREAKOUT
```

Tampilkan:

```text
Trades
Win Rate
Profit Factor
Average R
```

Dengan begitu kita bisa mengetahui setup mana yang benar-benar bekerja.

---

# 52. TRADE JOURNAL

Simpan:

```text
symbol
setup
signal_date
entry
stop
tp1
tp2
exit
result
R
score
```

---

# 53. GITHUB PREPARATION

Walaupun sekarang local-only, project harus aman untuk Git.

`.gitignore` wajib memasukkan:

```text
.env
__pycache__/
*.pyc

data/*.db
logs/*.log

.venv/
venv/
```

Database lokal:

```text
stock_signal.db
```

**JANGAN commit ke GitHub.**

---

# 54. REQUIREMENTS

Buat:

```text
requirements.txt
```

Minimal:

```text
fastapi
uvicorn
jinja2
sqlalchemy
pandas
numpy
yfinance
ta
python-dotenv
```

Tambahkan dependency lain hanya jika benar-benar dibutuhkan.

---

# 55. README

Buat README dengan instruksi sangat sederhana.

Contoh:

```bash
git clone <repository>

cd idx-signal

python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Install:

```bash
pip install -r requirements.txt
```

Run:

```bash
python run.py
```

Open:

```text
http://localhost:8000
```

---

# 56. DEVELOPMENT PHASE 1

KERJAKAN INI TERLEBIH DAHULU.

### STEP 1

Project structure.

### STEP 2

SQLite database.

### STEP 3

YahooFinanceProvider.

Test:

```text
BBCA.JK
BRMS.JK
HRUM.JK
```

### STEP 4

Daily OHLCV.

### STEP 5

Indicator Engine.

Hitung:

```text
EMA9
EMA21
MA20
MA50
RSI14
Volume MA20
Volume Ratio
```

### STEP 6

Base Screener.

### STEP 7

Ranking.

### STEP 8

Simple Dashboard.

### STEP 9

Manual Refresh.

### STEP 10

Validate results against actual chart.

Setelah semua berfungsi:

> PHASE 1 COMPLETE

Jangan lanjut Phase 2 sebelum Phase 1 stabil.

---

# 57. DEVELOPMENT PHASE 2

Setelah Phase 1 stabil:

### STEP 1

Intraday Yahoo data.

### STEP 2

1H trend.

### STEP 3

15M setup.

### STEP 4

5M confirmation.

### STEP 5

Pullback detector.

### STEP 6

Breakout detector.

### STEP 7

Support/resistance.

### STEP 8

Entry engine.

### STEP 9

SL/TP engine.

### STEP 10

Risk/Reward.

### STEP 11

Signal status.

### STEP 12

Chart.

Setelah stabil:

> PHASE 2 COMPLETE

---

# 58. DEVELOPMENT PHASE 3

Setelah Phase 2 stabil:

### STEP 1

Backtest engine.

### STEP 2

No-look-ahead validation.

### STEP 3

Trade simulation.

### STEP 4

Performance metrics.

### STEP 5

Trade journal.

### STEP 6

Pullback vs breakout comparison.

### STEP 7

Backtest dashboard.

Setelah stabil:

> PHASE 3 COMPLETE

---

# 59. DO NOT IMPLEMENT YET

Jangan implementasikan:

```text
AI
LLM
Chatbot

Stockbit integration
Broker integration
Automatic BUY
Automatic SELL

Supabase
PostgreSQL

Vercel
Cloud deployment

Authentication

Multi-user

Paid API

Realtime WebSocket

Order Book
Running Trade

Leverage
Margin
```

Semua itu future enhancement.

---

# 60. TESTING

Buat unit test minimal untuk:

```text
RSI calculation
EMA calculation
Volume Ratio
Screener
Score
Risk/Reward
Pullback detector
Breakout detector
```

Pastikan:

```text
same input
=
same output
```

---

# 61. ACCEPTANCE CRITERIA — PHASE 1

Phase 1 dianggap BERHASIL jika:

1. `python run.py` menjalankan aplikasi.
2. Browser dapat membuka localhost:8000.
3. SQLite dibuat otomatis.
4. Yahoo Finance berhasil mengambil data.
5. IDX ticker dapat di-scan.
6. EMA/RSI/Volume dihitung.
7. Screener menghasilkan kandidat.
8. Kandidat mendapatkan score.
9. Top 10 tampil di dashboard.
10. User dapat membuka detail saham.
11. Data source + timestamp terlihat.
12. Tidak ada AI.
13. Tidak ada hardcoded stock price.
14. Tidak membutuhkan API berbayar.
15. Tidak membutuhkan cloud.

---

# 62. ACCEPTANCE CRITERIA — PHASE 2

Phase 2 dianggap BERHASIL jika aplikasi dapat memberikan output seperti:

```text
SYMBOL:
HRUM

TREND:
BULLISH

SETUP:
PULLBACK

SCORE:
84

ENTRY ZONE:
880–885

STOP LOSS:
870

TP1:
900

TP2:
910

RR:
1:2

STATUS:
WAIT_PULLBACK
```

Angka harus berasal dari data yang sedang dianalisis.

---

# 63. ACCEPTANCE CRITERIA — PHASE 3

Phase 3 dianggap BERHASIL jika user dapat memilih periode historical dan mendapatkan:

```text
Strategy:
Pullback

Total Trades:
xxx

Win Rate:
xx%

Profit Factor:
x.xx

Average R:
x.xx

Max Drawdown:
xx%
```

serta daftar seluruh simulated trades.

---

# 64. IMPORTANT DEVELOPMENT INSTRUCTION

Jangan mencoba menyelesaikan seluruh project sekaligus.

Implementasikan secara incremental.

Urutan wajib:

```text
PHASE 1
↓
TEST
↓
VALIDATE
↓
PHASE 2
↓
TEST
↓
VALIDATE
↓
PHASE 3
```

Jika ada fitur yang tidak dapat berjalan karena keterbatasan Yahoo Finance:

**Jangan membuat workaround dengan fabricated data.**

Catat sebagai:

```text
LIMITATION
```

dan lanjutkan fitur yang dapat berjalan.

---

# 65. FINAL GOAL

Saat aplikasi lokal dibuka, user harus dapat:

```text
1. Klik UPDATE DATA

2. Klik RUN SCREENER

3. Melihat TOP CANDIDATES

4. Membuka kandidat

5. Melihat:
   Trend
   Momentum
   Score
   Setup
   Entry
   Stop Loss
   TP1
   TP2
   Risk/Reward

6. Memutuskan apakah ingin melakukan transaksi secara manual di broker.
```

Aplikasi hanya memberikan decision support.

Tidak melakukan transaksi saham secara otomatis.

Prioritas utama:

> **FUNCTIONAL → CORRECT → TESTABLE → SIMPLE**

Bukan:

> complex → beautiful → over-engineered
