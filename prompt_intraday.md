Saya ingin menambahkan fitur baru: INTRADAY DAY TRADE ENGINE ke aplikasi yang sudah ada.

PENTING:
JANGAN menghapus, mengganti, atau merusak Swing Trading Engine yang sekarang.

Strategi Daily yang sudah ada harus tetap berjalan seperti sekarang.

Kita hanya MENAMBAHKAN engine baru untuk day trading intraday.

==================================================
TUJUAN
==================================================

Aplikasi saat ini menggunakan Daily timeframe untuk menghasilkan swing signal.

Saya ingin menambahkan mode:

INTRADAY DAY TRADE

Tujuan intraday engine:

625 saham
→ Daily screening
→ pilih kandidat terbaik
→ Intraday monitoring
→ cari entry intraday
→ SL / TP intraday
→ signal BUY / WAIT / CANCEL
→ wajib exit sebelum market close

==================================================
ARSITEKTUR
==================================================

Pertahankan engine lama:

DAILY / SWING ENGINE
        ↓
Existing Signal
        ↓
Existing Score / Grade
        ↓
Existing Entry / SL / TP

Tambahkan engine baru:

DAILY FILTER
        ↓
INTRADAY WATCHLIST
        ↓
5m / 15m DATA
        ↓
INTRADAY INDICATORS
        ↓
INTRADAY SIGNAL ENGINE
        ↓
INTRADAY RISK MANAGEMENT
        ↓
INTRADAY SIGNAL
        ↓
OPTIONAL AI CONFIRMATION

==================================================
PHASE 1 — DAILY PRE-MARKET FILTER
==================================================

Gunakan existing Daily Screener sebagai filter awal.

Jangan membuat ulang seluruh Daily Screener.

Dari 625 saham, pilih kandidat untuk intraday berdasarkan existing technical score dan liquidity.

Target:

Top 20–30 saham

Watchlist harus berisi saham yang memiliki:
- Trend Daily yang sehat
- Liquidity yang memadai
- Volume yang memadai
- Existing Score yang baik
- Tidak terlalu extended
- Setup Daily yang masih relevan

Simpan informasi bahwa saham tersebut masuk:

INTRADAY WATCHLIST

==================================================
PHASE 2 — INTRADAY DATA
==================================================

Gunakan data intraday yang sudah tersedia di aplikasi.

Database sudah memiliki tabel:

intraday_prices

dan repository:

save_intraday_prices
get_recent_intraday_prices

Provider Yahoo juga sudah memiliki:

get_intraday_data()

Jangan membuat ulang komponen yang sudah tersedia.

Integrasikan komponen tersebut ke intraday engine.

Gunakan:

PRIMARY TIMEFRAME:
15m

OPTIONAL CONFIRMATION:
5m

Untuk tahap pertama, prioritaskan 15m agar sistem lebih stabil dan tidak terlalu noisy.

==================================================
PHASE 3 — MARKET SESSION
==================================================

Implementasikan market session IDX secara benar.

Gunakan timezone:

Asia/Jakarta

Aplikasi harus memahami minimal:

PRE-OPEN
08:45–08:59

SESSION 1
09:00–12:00

LUNCH BREAK
12:00–13:30

SESSION 2
13:30–15:49

PRE-CLOSING / POST-TRADING
15:50–16:15

Sesuaikan detail jam jika diperlukan berdasarkan konfigurasi yang sudah ada.

Jangan hardcode timezone selain Asia/Jakarta.

==================================================
PHASE 4 — OPENING RANGE
==================================================

Implementasikan Opening Range Breakout (ORB).

Gunakan candle 15 menit pertama setelah market open.

Opening Range:

OR_HIGH = High candle pertama
OR_LOW = Low candle pertama

Setelah Opening Range terbentuk:

BREAKOUT VALID hanya jika:

Price > OR_HIGH

DAN

Volume menunjukkan peningkatan yang valid.

Jangan menganggap hanya price crossing sebagai breakout valid.

Gunakan volume sebagai confirmation.

==================================================
PHASE 5 — VWAP
==================================================

Tambahkan indikator:

VWAP

VWAP harus reset setiap trading day.

Gunakan data intraday.

Formula:

VWAP =
Σ(Typical Price × Volume)
/
Σ(Volume)

Typical Price:

(High + Low + Close) / 3

Gunakan VWAP sebagai dynamic intraday reference.

==================================================
PHASE 6 — INTRADAY EMA
==================================================

Tambahkan:

EMA 9
EMA 21

pada timeframe 15m.

Gunakan untuk menentukan short-term intraday trend.

Contoh bullish alignment:

Price > EMA9 > EMA21

Contoh bearish:

Price < EMA9 < EMA21

==================================================
PHASE 7 — INTRADAY SETUPS
==================================================

Untuk V1 gunakan 2 setup utama.

--------------------------------
SETUP A — ORB BREAKOUT
--------------------------------

Conditions:

1. Opening Range sudah terbentuk
2. Price breaks above OR_HIGH
3. Volume confirmation valid
4. Price berada di atas VWAP
5. Intraday trend mendukung
6. Risk/Reward memenuhi minimum

Signal:

ORB_BREAKOUT

--------------------------------
SETUP B — VWAP / EMA PULLBACK
--------------------------------

Conditions:

1. Daily trend bullish
2. Intraday trend bullish
3. Price pullback menuju VWAP atau EMA9
4. Price menunjukkan rejection / recovery
5. Volume kembali meningkat
6. Risk/Reward memenuhi minimum

Signal:

VWAP_PULLBACK

Jangan membuat terlalu banyak setup pada V1.

==================================================
PHASE 8 — INTRADAY SCORE
==================================================

Buat scoring terpisah dari Daily Score.

JANGAN mengubah existing Daily Score.

Buat:

intraday_score = 0–100

Contoh komponen:

Daily Trend Alignment
Intraday Trend
VWAP Position
EMA Alignment
Volume Confirmation
Opening Range Confirmation
Entry Quality
Risk/Reward

Gunakan bobot yang masuk akal dan simpan sebagai konfigurasi agar mudah diubah.

Tampilkan secara terpisah:

Daily Score
Intraday Score

Jangan menggabungkannya menjadi satu score pada V1.

==================================================
PHASE 9 — INTRADAY ENTRY
==================================================

Entry harus berdasarkan harga intraday.

JANGAN menggunakan Daily Close sebagai entry intraday.

Entry harus memiliki:

entry_low
entry_high

Contoh:

Entry Zone:
2,540 – 2,550

Current Price:
2,545

Status:
READY

Jika harga sudah jauh melewati entry zone:

MISSED / DO NOT CHASE

Jika harga belum mencapai entry:

WAIT

==================================================
PHASE 10 — INTRADAY STOP LOSS
==================================================

SL harus berdasarkan struktur intraday.

Prioritaskan:

- Opening Range Low
- Intraday swing low
- VWAP
- EMA / structure

Jangan menggunakan Daily Swing Low sebagai SL utama untuk day trade.

SL harus realistis untuk pergerakan intraday.

==================================================
PHASE 11 — TAKE PROFIT
==================================================

Gunakan Risk/Reward intraday.

Minimal:

RR >= 1.5

Buat:

TP1
TP2

Tetapi jangan membuat TP terlalu jauh sehingga tidak realistis untuk day trade.

Pertimbangkan resistance intraday terdekat.

==================================================
PHASE 12 — SIGNAL STATUS
==================================================

Gunakan status khusus intraday:

WATCH
WAIT
READY
ACTIVE
TP1_HIT
TP2_HIT
STOP_LOSS
MISSED
CANCELLED
MARKET_CLOSED
FORCE_EXIT

Contoh:

WAIT:
Setup belum trigger.

READY:
Setup valid dan harga berada pada entry zone.

ACTIVE:
Entry sudah terjadi.

MISSED:
Harga sudah melewati entry zone tanpa entry.

CANCELLED:
Setup invalid sebelum entry.

FORCE_EXIT:
Waktu sudah mendekati market close.

==================================================
PHASE 13 — INVALIDATION
==================================================

Signal harus bisa menjadi invalid.

Contoh:

Jika setup breakout gagal dan price kembali di bawah OR_HIGH:

CANCELLED

Jika setup VWAP pullback gagal dan price breakdown VWAP:

CANCELLED

Jangan mempertahankan signal BUY yang sudah invalid.

==================================================
PHASE 14 — FORCE EXIT
==================================================

Ini WAJIB karena strategi ini adalah DAY TRADE.

Tidak boleh ada overnight position.

Menjelang market close:

status:

FORCE_EXIT

Jangan membuat signal baru mendekati waktu market close.

Gunakan waktu configurable.

Contoh:

NO NEW ENTRY:
setelah 15:00

FORCE EXIT:
15:30–15:45

Jadikan configurable di config.py.

==================================================
PHASE 15 — LIVE / DELAYED DATA
==================================================

PENTING:

Yahoo Finance memiliki delay.

Jangan menyebut Yahoo sebagai true realtime.

Tampilkan:

DATA SOURCE:
Yahoo Finance

DATA STATUS:
Delayed

Intraday engine harus dirancang untuk polling 5m / 15m.

Jangan membuat sistem seolah-olah memiliki tick-by-tick realtime data.

Arsitektur harus memungkinkan provider realtime diganti di masa depan.

==================================================
PHASE 16 — DASHBOARD
==================================================

Tambahkan mode:

[ SWING ]
[ INTRADAY ]

Mode Swing:
gunakan existing engine.

Mode Intraday:
gunakan Intraday Engine.

Dashboard Intraday menampilkan:

INTRADAY WATCHLIST

Symbol
Daily Score
Intraday Score
Setup
Current Price
VWAP
OR High
OR Low
EMA9
EMA21
Volume Ratio
Entry Zone
SL
TP1
TP2
RR
Status

Contoh:

CMRY
Daily Score: 91
Intraday Score: 87

Setup:
VWAP_PULLBACK

Price:
4,700

VWAP:
4,680

Entry:
4,680–4,710

SL:
4,630

TP1:
4,790

TP2:
4,850

RR:
1:1.7

Status:
READY

==================================================
PHASE 17 — CHART
==================================================

Pada stock detail page tambahkan timeframe:

1D
15m
5m

Untuk Intraday:

Tampilkan pada chart:

- Candlestick
- VWAP
- EMA9
- EMA21
- OR High
- OR Low
- Entry
- SL
- TP

Gunakan TradingView Lightweight Charts yang sudah digunakan aplikasi.

==================================================
PHASE 18 — AI
==================================================

JANGAN gunakan AI sebagai pengganti Intraday Rule Engine.

Rule Engine tetap menentukan apakah setup valid.

AI hanya menjadi optional second opinion.

Flow:

Intraday Engine
↓
Top Intraday Candidates
↓
AI Analysis
↓
AI Priority / Explanation

AI dapat menganalisis:

- Daily trend
- Intraday trend
- VWAP
- EMA
- Volume
- ORB
- Entry quality
- Risk/Reward
- Setup consistency

AI tidak boleh:
- mengubah Entry
- mengubah SL
- mengubah TP
- mengubah Intraday Score
- membuat data harga

==================================================
PHASE 19 — DATA STORAGE
==================================================

Gunakan SQLite yang sudah ada:

data/stock_signal.db

Jangan membuat database baru.

Gunakan tabel intraday_prices yang sudah ada.

Jika diperlukan, tambahkan tabel:

intraday_signals

Fields minimal:

id
symbol
trading_date
timestamp
setup_type
daily_score
intraday_score
current_price
entry_low
entry_high
stop_loss
tp1
tp2
risk_reward
vwap
or_high
or_low
ema9
ema21
volume_ratio
status
created_at
updated_at

Jangan menghapus historical signals.

==================================================
PHASE 20 — API
==================================================

Tambahkan endpoint:

GET /api/intraday-signals

GET /api/intraday-status

GET /api/intraday-data/{symbol}

POST /api/run-intraday-scan

Gunakan struktur FastAPI yang sudah ada.

==================================================
PHASE 21 — POLLING
==================================================

Jangan polling 625 saham.

Hanya polling:

Top 20–30 Intraday Watchlist.

Contoh:

625 saham
↓
Daily Screener
↓
Top 20
↓
Intraday polling

Ini untuk menghemat resource dan API request.

Polling harus berhenti ketika market closed.

Jangan melakukan polling terus-menerus di luar jam trading.

==================================================
PHASE 22 — DO NOT BREAK EXISTING SYSTEM
==================================================

Existing Swing Engine harus tetap berfungsi.

Existing:

Daily Screener
Daily Score
Swing Signal
Backtest
AI Analyst
Stock Detail
Market Data

tidak boleh rusak.

Intraday Engine harus modular dan terpisah.

==================================================
IMPLEMENTATION ORDER
==================================================

Implementasikan secara bertahap:

STEP 1
Market session engine

STEP 2
Intraday data downloader untuk watchlist

STEP 3
15m intraday indicator engine

STEP 4
VWAP

STEP 5
Opening Range

STEP 6
Intraday EMA

STEP 7
ORB Breakout

STEP 8
VWAP Pullback

STEP 9
Intraday scoring

STEP 10
Intraday Entry / SL / TP

STEP 11
Signal status & invalidation

STEP 12
Force Exit

STEP 13
Intraday dashboard

STEP 14
Intraday chart

STEP 15
Testing

STEP 16
Optional AI confirmation

==================================================
IMPORTANT DEVELOPMENT RULE
==================================================

Do NOT implement everything blindly in one large change.

First inspect the existing code and reuse existing components.

Before modifying each file, understand its current implementation.

Do not duplicate:
- Yahoo provider
- SQLite connection
- Indicator utilities
- Existing configuration
- Existing chart component
- Existing signal infrastructure

Create new modules only where necessary.

After each major step, ensure the existing Swing Trading functionality still works.

The final architecture should be:

625 IDX Stocks
        ↓
DAILY SCREENER
        ↓
TOP 20–30 WATCHLIST
        ↓
┌───────────────────────┐
│                       │
│ Existing Swing Engine │
│                       │
└───────────────────────┘

AND

TOP 20–30 WATCHLIST
        ↓
15m / 5m Intraday Data
        ↓
VWAP + EMA + ORB + Volume
        ↓
INTRADAY ENGINE
        ↓
Intraday Signal
        ↓
Optional AI Confirmation
        ↓
DAY TRADE DECISION

The goal is a TRUE INTRADAY DAY TRADE ENGINE,
while preserving the existing Swing Trading Engine.