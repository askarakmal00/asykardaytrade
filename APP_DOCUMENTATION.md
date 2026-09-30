# AsykarDayTrade — Dokumentasi Lengkap Aplikasi

> **Platform:** Web App (lokal), FastAPI + SQLite + Yahoo Finance + Google Gemini AI  
> **Tujuan:** Sistem sinyal trading harian untuk saham IDX (Bursa Efek Indonesia), dengan screener teknikal otomatis, manajemen portofolio, AI analysis berbasis berita realtime, dan backtesting.

---

## Daftar Isi

1. [Arsitektur Sistem](#1-arsitektur-sistem)
2. [Database & Model Data](#2-database--model-data)
3. [Konfigurasi (.env)](#3-konfigurasi-env)
4. [Universe Saham](#4-universe-saham)
5. [Pipeline Data Market](#5-pipeline-data-market)
6. [Indikator Teknikal](#6-indikator-teknikal)
7. [Mesin Sinyal (Signal Engine)](#7-mesin-sinyal-signal-engine)
8. [Screener & Ranking](#8-screener--ranking)
9. [Halaman & Fitur UI](#9-halaman--fitur-ui)
10. [AI Analysis — Saham Individual](#10-ai-analysis--saham-individual)
11. [AI Analysis — Portfolio](#11-ai-analysis--portfolio)
12. [Manajemen Portfolio (CRUD)](#12-manajemen-portfolio-crud)
13. [Backtesting Engine](#13-backtesting-engine)
14. [REST API Endpoints](#14-rest-api-endpoints)
15. [Alur Kerja End-to-End](#15-alur-kerja-end-to-end)
16. [Struktur Folder](#16-struktur-folder)

---

## 1. Arsitektur Sistem

```
Browser
  │
  ▼
FastAPI (app/main.py) — Uvicorn, port 8000
  │
  ├── Jinja2 Templates (app/templates/*.html)
  ├── Static Files (app/static/)
  │
  ├── Services Layer
  │   ├── market_data.py          → Download OHLCV dari Yahoo Finance (batch)
  │   ├── scanner_service.py      → Jalankan screener + signal engine di semua saham
  │   ├── ai_analyst.py           → AI analisis saham individual (Gemini + Google News)
  │   ├── portfolio_service.py    → Hitung P/L, enrichment data portfolio
  │   └── portfolio_ai_analyst.py → AI analisis portfolio (Gemini)
  │
  ├── Strategy Layer
  │   ├── signal_engine.py        → Scoring engine (0-100), grade, status, levels
  │   ├── pullback.py             → Deteksi setup PULLBACK
  │   ├── breakout.py             → Deteksi setup BREAKOUT
  │   ├── support_resistance.py   → Hitung S/R dari swing high/low + EMA
  │   └── risk_management.py      → Hitung Entry Zone, SL, TP1, TP2, R/R
  │
  ├── Indicators Layer
  │   ├── trend.py    → EMA9, EMA21, MA20, MA50, EMA21 Slope, Dist_EMA9_Pct, ATR
  │   ├── momentum.py → RSI14, Stochastic RSI (K, D)
  │   └── volume.py   → Volume MA20, Volume Ratio, Estimated Value
  │
  ├── Backtest Layer
  │   ├── engine.py   → Simulasi trade candle-by-candle (no look-ahead bias)
  │   └── metrics.py  → Win rate, profit factor, expectancy, equity curve
  │
  ├── Providers Layer
  │   └── yahoo.py    → YahooFinanceProvider (daily OHLCV + live quote + intraday)
  │
  └── Database Layer (SQLite)
      ├── connection.py   → SQLAlchemy engine + session
      ├── models.py       → ORM models (5 tabel)
      └── repositories.py → CRUD functions
```

**Tech Stack:**

| Layer | Library |
|---|---|
| Framework | FastAPI + Uvicorn |
| Template | Jinja2 |
| Database | SQLite (via SQLAlchemy ORM) |
| Market Data | yfinance (Yahoo Finance) |
| Indicators | ta (Technical Analysis library) |
| AI | Google Gemini API (Free Tier) |
| News | Google News RSS |
| Charts | Lightweight Charts (TradingView) |
| UI | Bootstrap 5 + Bootstrap Icons |

---

## 2. Database & Model Data

Database: **SQLite** tersimpan di `data/stock_signal.db` (lokal) atau `/tmp/stock_signal.db` (Vercel).

### Tabel `symbols`
Daftar saham yang terdaftar di universe screener.

| Kolom | Tipe | Keterangan |
|---|---|---|
| `id` | Integer PK | Auto increment |
| `symbol` | String UNIQUE | Ticker, e.g. `BBCA.JK` |
| `name` | String | Nama perusahaan |
| `sector` | String | Sektor IDX |
| `is_active` | Boolean | Aktif/nonaktif di screener |
| `created_at` / `updated_at` | DateTime | Timestamp |

### Tabel `daily_prices`
Candle OHLCV harian per saham.

| Kolom | Tipe | Keterangan |
|---|---|---|
| `symbol_id` | FK → symbols | Relasi ke saham |
| `date` | DateTime | Tanggal candle (Asia/Jakarta, naive midnight) |
| `open/high/low/close/volume` | Float | Data OHLCV |

> **Unique constraint:** `(symbol_id, date)` — upsert otomatis saat update data.

### Tabel `intraday_prices`
Candle intraday (15m, 1h) — schema ada di DB, belum digunakan di screener utama.

| Kolom | Tipe | Keterangan |
|---|---|---|
| `symbol_id` | FK → symbols | Relasi ke saham |
| `timestamp` | DateTime | Waktu candle |
| `interval` | String | `'15m'`, `'1h'`, dll |

### Tabel `signals`
Hasil sinyal scanner per run.

| Kolom | Tipe | Keterangan |
|---|---|---|
| `symbol_id` | FK → symbols | Relasi ke saham |
| `score` | Integer | Skor sinyal 0-100 |
| `grade` | String | `A+`, `A`, `WATCH`, `LOW QUALITY`, `NO TRADE` |
| `setup` | String | `PULLBACK`, `BREAKOUT`, `NONE` |
| `status` | String | `READY`, `WAIT_PULLBACK`, `WAIT_BREAKOUT`, `WATCH`, `NO_TRADE` |
| `entry_low/high` | Float | Zona entry |
| `stop_loss/tp1/tp2` | Float | Level manajemen risiko |
| `risk_reward` | Float | Rasio risk/reward |
| `rsi/ema9/ema21/volume_ratio` | Float | Indikator kunci |
| `reason` | Text | Penjelasan signal (JSON/multiline) |

### Tabel `scan_runs`
Log setiap kali screener dijalankan.

| Kolom | Tipe | Keterangan |
|---|---|---|
| `started_at` / `completed_at` | DateTime | Waktu proses |
| `symbols_scanned` | Integer | Total saham yang discan |
| `symbols_passed` | Integer | Yang lolos screener |
| `status` | String | `running`, `completed`, `failed` |
| `error_count` | Integer | Jumlah error saat scan |

### Tabel `portfolio_holdings`
Posisi saham yang dimiliki user.

| Kolom | Tipe | Keterangan |
|---|---|---|
| `symbol` | String | Ticker saham, e.g. `BBCA.JK` |
| `company_name` | String (opsional) | Nama perusahaan |
| `quantity_lots` | Integer | Jumlah LOT (1 lot = 100 saham) |
| `avg_buy_price` | Float | Harga beli rata-rata per saham |
| `buy_date` | String | Format `YYYY-MM-DD` |
| `target_price` | Float (opsional) | Target harga jual |
| `stop_loss_price` | Float (opsional) | Stop loss user |
| `notes` | Text (opsional) | Catatan bebas |
| `is_active` | Boolean | Soft delete — data tetap ada di DB |

> **Konvensi IDX:** 1 lot = 100 saham. Semua kalkulasi P/L menggunakan `lots × 100 × price`.

---

## 3. Konfigurasi (.env)

File `.env` di root project mengontrol semua parameter sistem:

```env
# Screener Filters
MIN_PRICE=200           # Harga minimum saham (IDR)
RSI_MIN=50              # RSI minimum yang diterima screener
RSI_MAX=70              # RSI maximum (batas overbought)
MIN_VOLUME=1000000      # Volume minimum (1 juta saham/hari)
MIN_VALUE=10000000000   # Nilai transaksi minimum Rp10 Miliar/hari
MIN_VOLUME_RATIO=1.5    # Volume hari ini vs rata-rata 20 hari

# EMA Settings
EMA_FAST=9
EMA_SLOW=21

# Signal Scoring
MIN_SIGNAL_SCORE=75     # Score minimum untuk status READY
MIN_RISK_REWARD=1.5     # Minimum R/R ratio

# AI Settings
AI_ENABLED=true
GEMINI_API_KEY=...      # Dari https://aistudio.google.com/app/apikey
GEMINI_MODEL=gemini-2.5-flash
```

---

## 4. Universe Saham

File sumber: `data/idx_symbols.csv`

```
symbol,name,sector
BBCA.JK,Bank Central Asia Tbk,Financials
TLKM.JK,Telkom Indonesia Tbk,Communication Services
...
```

- **Total:** ~935–959 saham aktif IDX
- **Seed otomatis:** Setiap server start, fungsi `seed_symbols_from_csv()` membaca CSV dan **upsert** ke tabel `symbols` — simbol baru ditambahkan, yang sudah ada di-update nama/sektornya
- **Format ticker:** Semua menggunakan suffix `.JK` (standar Yahoo Finance untuk IDX)
- **Edit universe:** Cukup edit `data/idx_symbols.csv` dan restart server / call update-data

---

## 5. Pipeline Data Market

### 5.1 Download Harian (Batch)

Dipicu via tombol **"Update Market Data"** di UI atau `POST /api/update-data`.

**Alur:**
1. Ambil semua symbol aktif dari DB
2. Bagi jadi chunks 50 ticker
3. Untuk setiap chunk: `yf.download(chunk, period="1y", interval="1d", threads=True)`
4. Hasil disimpan ke `daily_prices` via **upsert** (conflict on `symbol_id + date` → update)
5. Setelah download selesai → **otomatis jalankan screener**
6. Progress bisa dipantau via polling `GET /api/status`

**Fallback:** Jika batch download gagal → coba per-ticker satu-satu menggunakan `yf.Ticker.history()`.

**Timezone:** Semua timestamp dikonversi ke `Asia/Jakarta` lalu disimpan sebagai naive midnight datetime (tanpa timezone) untuk kompatibilitas SQLite.

### 5.2 Live Quote (Per Saham)

Untuk halaman detail saham `/stock/{symbol}`, harga realtime diambil dari Yahoo Finance via `yf.Ticker.fast_info`:

| Field | Sumber | Keterangan |
|---|---|---|
| `current_price` | `fast_info.last_price` | Harga terakhir (delayed ~15-20 menit) |
| `previous_close` | `fast_info.previous_close` | Penutupan hari sebelumnya |
| `day_high` / `day_low` | `fast_info` | High/low hari ini |

> ⚠️ **Penting:** `daily_prices.close` adalah **sesi sebelumnya** (bukan harga terkini). `current_price` hanya di-fetch per saham di halaman detail untuk menghindari rate limiting saat scan 900+ saham.

---

## 6. Indikator Teknikal

Semua indikator dihitung dari data harian di DB menggunakan library `ta`.

### 6.1 Trend Indicators (`app/indicators/trend.py`)

| Indikator | Window | Kegunaan |
|---|---|---|
| `EMA9` | 9 hari | Support/resistance dinamis jangka pendek |
| `EMA21` | 21 hari | Support/resistance dinamis jangka menengah |
| `MA20` | 20 hari (SMA) | Konfirmasi tren harian |
| `MA50` | 50 hari (SMA) | Konfirmasi tren jangka menengah |
| `EMA21_Slope` | `EMA21.diff(3)` | Arah kemiringan tren (positif = naik) |
| `Dist_EMA9_Pct` | `(close - EMA9) / EMA9 × 100` | Seberapa jauh harga dari EMA9 (%) |
| `ATR` | 14 hari | Average True Range untuk volatilitas & kalkulasi SL |

### 6.2 Momentum Indicators (`app/indicators/momentum.py`)

| Indikator | Window | Kegunaan |
|---|---|---|
| `RSI14` | 14 hari | Kekuatan momentum (50-70 = zona bullish optimal) |
| `Stoch_RSI_K` | 14 hari, smooth=3 | Oscillator momentum (0-100) |
| `Stoch_RSI_D` | Signal line dari K | Konfirmasi crossover |

### 6.3 Volume Indicators (`app/indicators/volume.py`)

| Indikator | Rumus | Kegunaan |
|---|---|---|
| `Volume_MA20` | SMA(volume, 20) | Baseline volume rata-rata 20 hari |
| `Volume_Ratio` | `volume / Volume_MA20` | Berapa kali lipat volume vs rata-rata |
| `Volume_Change_Pct` | `volume.pct_change() × 100` | Perubahan volume % |
| `Estimated_Value` | `close × volume` | Estimasi nilai transaksi harian (IDR) |

---

## 7. Mesin Sinyal (Signal Engine)

File: `app/strategy/signal_engine.py`  
Fungsi: `evaluate_signal(df: DataFrame) → Dict`

### 7.1 Support & Resistance (`support_resistance.py`)

Dihitung dari 10 candle terakhir:
- **Support:** minimum dari `[swing_low, EMA21, prev_low]` yang ≤ harga sekarang  
  → `support_low = support_val × 0.99`, `support_high = support_val × 1.005`
- **Resistance:** maximum dari `[swing_high, prev_high]` yang ≥ harga sekarang  
  → `resistance_low = resist_val × 0.995`, `resistance_high = resist_val × 1.01`

### 7.2 Setup Detection

#### PULLBACK Setup (`pullback.py`)

Semua kondisi berikut harus terpenuhi:
```
trend_bullish    = price >= EMA9 × 0.985  AND  EMA9 >= EMA21 × 0.99
support_valid    = price >= support_low × 0.99
near_ema_pullback = |Dist_EMA9_Pct| <= 2.5%  OR  (EMA21×0.98 <= price <= EMA9×1.01)
is_pullback      = trend_bullish AND support_valid AND (near_ema_pullback OR dist_ema9 <= 3%)
```

**Score boost:** +15 (base) + 5 (support valid) + 5 (RSI 45-68) = **max +25**

**Status:**
- `READY` → momentum_recovering (RSI 45-68) + near_ema_pullback
- `WAIT_PULLBACK` → valid setup tapi harga belum dalam zona entry

#### BREAKOUT Setup (`breakout.py`)

```
near_resistance = price >= resistance_low × 0.98  OR  high >= prev_high × 0.995
volume_surge    = Volume_Ratio >= 1.4
consolidation   = range(5 candles) / swing_low <= 8%
is_breakout     = near_resistance AND (volume_surge OR consolidation) AND price >= EMA9
```

**Score boost:** +15 (base) + 5 (volume surge) + 5 (konsolidasi) = **max +25**

**Status:**
- `READY` → price >= prev_high + volume_surge + Dist_EMA9 <= 4%
- `WAIT_BREAKOUT` → setup valid tapi belum breakout tuntas

### 7.3 Risk Management (`risk_management.py`)

#### PULLBACK Trade Levels:
```
entry_low  = min(price, max(EMA21, EMA9 × 0.995))
entry_high = max(price, EMA9 × 1.005)
stop_loss  = min(swing_low × 0.99, support_low × 0.99, entry_low − 1.2 × ATR)
risk       = entry_high − stop_loss
TP1        = entry_high + (risk × 1.5)
TP2        = max(resistance_high, entry_high + (risk × 2.0))
```

#### BREAKOUT Trade Levels:
```
entry_low  = price × 0.995
entry_high = price × 1.005
stop_loss  = min(entry_low × 0.97, entry_low − 1.5 × ATR)
risk       = entry_high − stop_loss
TP1        = entry_high + (risk × 1.5)
TP2        = entry_high + (risk × 2.2)
```

**Risk/Reward:** `(TP1 − entry_high) / (entry_high − stop_loss)`

### 7.4 Scoring Engine (0–100 poin)

| Komponen | Max Poin | Kondisi |
|---|---|---|
| **A. TREND** | **25** | |
| Price > EMA9 | +8 | Support dinamis terjaga |
| EMA9 > EMA21 | +8 | Bullish alignment |
| EMA21 Slope > 0 | +5 | Tren sedang naik |
| Close > MA20 > MA50 | +4 | Konteks bullish jangka menengah |
| **B. MOMENTUM** | **20** | |
| RSI 50-70 | +10 | Zona bullish optimal |
| RSI 55-72 | +5 | Akselerasi momentum positif |
| Stoch K > Stoch D, K ≥ 20 | +5 | Bullish crossover/recovery |
| **C. LIQUIDITY** | **20** | |
| Est. Value ≥ Rp10B | +7 | Cukup likuid |
| Volume ≥ 1 juta saham | +5 | |
| Volume Ratio ≥ 1.5x | +8 | (+4 jika ≥ 1.0x) |
| **D. SETUP** | **25** | Output dari PULLBACK/BREAKOUT engine |
| **E. RISK/REWARD** | **10** | +10 jika R/R ≥ 2.0; +5 jika ≥ 1.5 |
| **PENALTIES** | | |
| RSI > 75 | −10 | Extreme overbought |
| RSI > 70 | (warning) | Overbought |
| Dist_EMA9 > 5% | −20 | Severely extended |
| Dist_EMA9 > 3% | −10 | Extended |
| Est. Value < Rp5B atau Vol < 500K | −20 | Low liquidity |

**Final Score:** `max(0, min(100, score))` (Quality Score, BUKAN probabilitas profit)

### 7.5 Grade Classification

| Score | Grade | Arti |
|---|---|---|
| ≥ 85 | **A+** | Setup sangat ideal |
| ≥ 75 | **A** | Setup baik |
| ≥ 65 | **WATCH** | Perlu dipantau |
| ≥ 50 | **LOW QUALITY** | Setup lemah |
| < 50 | **NO TRADE** | Tidak layak |

> **Catatan P0:** Grade menunjukkan kualitas setup berdasarkan scoring engine, BUKAN otomatis berarti BUY. Misalnya: `Grade A` dengan status `WAIT_PULLBACK` adalah valid (kualitas setup bagus tapi entry belum terpicu).

### 7.6 Status Resolution (SINGLE SOURCE OF TRUTH)

Konfigurasi `config.MIN_SIGNAL_SCORE = 75` adalah **satu-satunya acuan** penentuan status READY:

| Status | Kondisi |
|---|---|
| `WAIT_PULLBACK` | Dist_EMA9 > 5% |
| `NO_TRADE` | R/R < MIN_RISK_REWARD DAN setup != NONE |
| `READY` | prelim_status == READY DAN score ≥ MIN_SIGNAL_SCORE (75) |
| `WAIT_PULLBACK/BREAKOUT` | prelim dari setup engine |
| `WATCH` | score ≥ 65 |
| `NO_TRADE` | Semua kondisi di atas tidak terpenuhi |

### 7.7 Entry Validity (P0 Enhancement)

Menentukan apakah harga saat ini masih berada dalam zona eksekusi yang aman:

| Nilai | Definisi & Tindakan |
|---|---|
| `VALID` | Harga masih berada di dalam zona entry yang direncanakan. Action: `CONSIDER_ENTRY`. |
| `MISSED` | Harga sudah naik menembus batas atas entry zone (>1.5%). Action: `DO_NOT_CHASE`. |
| `EXTENDED` | Harga terlalu jauh dari EMA9 dynamic support (>3%). Action: `WAIT_REENTRY`. |
| `INVALID` | Harga tembus di bawah Stop Loss atau setup rusak. Action: `DO_NOT_ENTER`. |
| `UNKNOWN` | Data historis atau harga tidak mencukupi. |

### 7.8 Signal Freshness (P0 Enhancement)

Sinyal diukur usianya dari timestamp pembuatan (`signal_generated_at`):

| Label | Usia Sinyal | Keterangan |
|---|---|---|
| `FRESH` | &le; 60 menit | Sinyal baru dan sangat relevan untuk eksekusi sesi aktif. |
| `AGING` | 60 – 180 menit | Sinyal masih valid, disarankan cek chart terkini. |
| `STALE` | &gt; 180 menit | Sinyal lama, lakukan re-run scanner sebelum eksekusi. |

### 7.9 Next Action (P0 Guidance)

Trader langsung diarahkan ke tindakan konkret tanpa perlu menebak interpretasi angka:
- `CONSIDER_ENTRY`: Setup READY dan harga dalam zona VALID.
- `WAIT_PULLBACK`: Setup pullback valid, tunggu harga masuk zona beli.
- `WAIT_BREAKOUT`: Menguji resistance, tunggu breakout terkonfirmasi.
- `MONITOR`: Setup watchlist dalam pemantauan.
- `DO_NOT_CHASE`: Entry sudah terlewat (MISSED), dilarang mengejar harga.
- `WAIT_REENTRY`: Harga over-extended, tunggu koreksi kembali mendekati support.
- `DO_NOT_ENTER`: Tidak memenuhi syarat manajemen risiko.
- `RECHECK_SIGNAL`: Sinyal sudah kedaluwarsa (STALE), perbarui data market.

---

## 8. Screener & Ranking

### 8.1 Base Screener (`app/scanner/screener.py`)

Filter minimum (semua harus terpenuhi):
- Harga ≥ `MIN_PRICE` (Rp200)
- RSI antara `RSI_MIN` (50) dan `RSI_MAX` (70)
- Volume ≥ `MIN_VOLUME` (1 juta saham)
- Estimated Value ≥ `MIN_VALUE` (Rp10 Miliar)
- Volume Ratio ≥ `MIN_VOLUME_RATIO` (1.5x)

### 8.2 Run Scanner & Ranking Priority (`scanner_service.run_scanner` + `ranking.py`)

Untuk setiap saham aktif di DB:
1. Load data historis dari `daily_prices`
2. Hitung semua indikator (trend, momentum, volume)
3. Jalankan screener + signal engine (hasilkan score, grade, status, entry_validity, freshness, next_action)
4. Simpan hasil ke tabel `signals`
5. **Ranking Prioritas (P0):**
   ```
   READY status  →  ENTRY VALID  →  FRESH  →  Score descending  →  R:R descending
   ```
   Dengan demikian, saham yang siap dieksekusi (READY + VALID + FRESH) selalu muncul di urutan teratas dibandingkan saham berskor tinggi yang entry-nya sudah terlewat.

### 8.3 Output Scanner

```python
{
  "ready_candidates": [...],  # Status READY + score ≥ 75 (sudah diranking prioritas)
  "wait_candidates": [...],   # Status WAIT_PULLBACK / WAIT_BREAKOUT
  "watch_candidates": [...],  # Status WATCH
  "no_trade_candidates": [...], # Status NO_TRADE / DATA_UNAVAILABLE
  "passed": [...],            # Lolos screener dasar
  "all": [...],               # Semua saham
  "scanned_count": 959,
  "ready_count": 12,
  "passed_count": 45,
  "wait_count": 18,
  "watch_count": 87,
  "scan_time": "2026-09-12T09:15:00"
}
```

---

## 9. Halaman & Fitur UI (P0 Redesign)

### 9.1 Dashboard (`/`)
Workflow interaktif terpadu:
1. **Section 1 — Market Status**: Status market realtime (OPEN / CLOSED / PRE-MARKET WIB), waktu update data & scan, tombol "Update Market Data" dan "Run Screener".
2. **Section 2 — What Should I Do Today?**: 4 kartu kelompok aksi:
   - 🟢 `READY TO CONSIDER` (Kandidat eksekusi langsung)
   - 🟡 `WAIT FOR SETUP` (Kandidat menunggu trigger)
   - ⚪ `WATCHLIST` (Kandidat tren positif)
   - 🔴 `NO TRADE` (Saham yang tereliminasi)
3. **Section 3 — Top Actionable Signals Table**: Tabel sinyal terurut berdasarkan prioritas eksekusi, dilengkapi indikator Freshness, Entry Validity, dan Next Action.
4. **Empty States yang Informatif**: Penjelasan eksplisit dan saran tindakan jika belum ada sinyal READY.

### 9.2 Screener (`/screener`)
- Filter tombol cepat: ALL, READY, WAIT, WATCH, NO TRADE
- Filter dropdown: Grade, Setup, Entry Validity, Freshness
- Kolom: Symbol, Price, Score, Grade, Setup, Status, Entry Zone, SL, TP1, RR, Freshness, Next Action

### 9.3 Detail Saham (`/stock/{symbol}`)
Workflow 30 detik untuk pengambilan keputusan:
1. **Header**: Symbol, Grade, Setup, Status, Freshness, Harga Terkini vs Daily Close, Signal Quality Score (/100).
2. **What Is Happening?**: Rangkuman naratif berbasis data teknikal aktual.
3. **Next Action & Entry Status**: Banner dinamis instruksi trading (CONSIDER ENTRY / DO NOT CHASE / WAIT RE-ENTRY).
4. **Trade Plan Visual Progression**:
   `ENTRY ZONE` &rarr; `STOP LOSS` &rarr; `TAKE PROFIT 1` &rarr; `TAKE PROFIT 2` &rarr; `RISK/REWARD`
5. **Why This Signal?**: Bukti teknikal (checklist hijau) dan faktor risiko/kehati-hatian (checklist merah).
6. **Chart & Technical Metrics**: TradingView Lightweight Charts + EMA9/21 overlay + RSI, Volume Ratio, S/R.
7. **Historical Strategy Backtest**: Simulasi historis per-saham.
8. **AI Context & News Sentiment**: Decision-support layer dengan perbandingan eksplisit **System Signal vs AI View** (peringatan khusus jika AI menyarankan HOLD saat sinyal sistem READY).


### 9.6 Backtest (`/backtest`)
- Filter: Symbol, Setup (ALL/PULLBACK/BREAKOUT), Min Score, Max Hold Days
- Output: Equity curve chart, per-trade log table, summary metrics

### 9.7 Debug Market Data (`/debug/market-data/{symbol}`)
- Diagnostic: bandingkan `fast_info.last_price` vs `daily_close` vs `previous_close`
- 10 candle terakhir untuk Daily, 1H, 15M
- Status market (REGULAR / CLOSED) berdasarkan jam IDX (09:00-16:00 WIB)

---

## 10. AI Analysis — Saham Individual

File: `app/services/ai_analyst.py`

### 10.1 Alur Kerja

```
User buka /stock/{symbol}
  → Page load → JS fetch /api/ai-analysis/{TICKER}
  → ai_analyst.analyze_stock(signal_data)
  → fetch_stock_news(ticker)         ← Google News RSS (async, timeout 5s)
  → _build_prompt(signal + news)     ← Bangun prompt lengkap
  → Gemini API generateContent       ← AI generate (timeout 35s)
  → _parse_ai_response(raw_text)     ← Parse JSON + normalise
  → Return JSON ke browser
  → Tampil di AI Panel (lazy loaded)
```

### 10.2 News Fetcher (`fetch_stock_news`)

- **Sumber:** `https://news.google.com/rss/search?q={TICKER}+saham&hl=id&gl=ID&ceid=ID:id`
- **Filter:** Hanya berita dalam **3.5 hari terakhir** (via `pubDate`)
- **Limit:** Maksimal 5 headline teratas
- **Fallback:** Jika gagal/timeout → `"Tidak ada berita signifikan"`

**Contoh output:**
```
- BCA Siapkan Buyback BBCA Rp5 Triliun hingga Maret 2027 (Bloomberg Technoz)
- Investor asing outflow, BBCA top net sell Rp550 miliar (IDNFinancials)
- Saham BBCA Tiba-tiba Anjlok 2% Lebih, Asing Net Sell Jumbo (CNBC Indonesia)
```

### 10.3 Prompt Template

```
Analisis saham {TICKER} ({SECTOR}) untuk keputusan trading hari ini.

DATA TEKNIKAL:
- Harga: Rp{PRICE} | EMA9: Rp{EMA9} | EMA21: Rp{EMA21} | RSI: {RSI}
- Volume: {VOLUME} ({VOLUME_CHANGE}% vs rata-rata)
- Support: {SUPPORT} | Resistance: {RESISTANCE}
- Entry zone: Rp{ENTRY_LOW} – Rp{ENTRY_HIGH} | SL: Rp{SL} | TP1: Rp{TP1} | TP2: Rp{TP2}

SIGNAL SISTEM:
- Setup: {SETUP} | Grade: {GRADE} | Score: {SCORE}/100 | Status: {STATUS}
- Risk/Reward: 1:{RR}

BERITA TERKINI (3 hari terakhir):
{NEWS_HEADLINES}

INSTRUKSI:
- Wajib kaitkan rekomendasi dengan berita di atas jika ada, sebutkan judul/sumbernya secara spesifik.
- Jika tidak ada berita relevan, nyatakan itu secara eksplisit.
- DILARANG kalimat generik seperti "sensitif terhadap fluktuasi global" tanpa data konkret.
```

### 10.4 Output JSON Schema

```json
{
  "recommendation": "BUY | HOLD | SELL",
  "confidence": 65,
  "risks": [
    "Risiko spesifik mengacu data/berita nyata",
    "Risiko 2",
    "Risiko 3"
  ],
  "opportunities": [
    "Peluang spesifik mengacu berita nyata",
    "Peluang 2"
  ],
  "news_context": "1-2 kalimat yang secara eksplisit menyebut berita nyata."
}
```

**Legacy aliases** disertakan untuk backward compatibility template HTML:
- `ai_recommendation` = `recommendation`
- `ai_confidence` = `confidence`
- `ai_risks` = `risks`
- `ai_opportunities` = `opportunities`
- `ai_market_context` = `news_context`

### 10.5 Tampilan Badge di UI

| Nilai | Warna | Label |
|---|---|---|
| `BUY` | Hijau | ⚡ BUY |
| `HOLD` | Kuning | ⏳ HOLD |
| `SELL` | Merah | 🚫 SELL |

**Confidence bar:**
- ≥ 70 → Hijau (`#22c55e`)
- ≥ 50 → Kuning (`#f59e0b`)
- < 50 → Merah (`#ef4444`)

---

## 11. AI Analysis — Portfolio

File: `app/services/portfolio_ai_analyst.py`

### 11.1 Per-Posisi (`analyze_position`)

Dijalankan saat user klik **"Analisis AI"** pada satu posisi.

**Input ke AI:** Symbol, lot, harga beli, harga sekarang (delayed), P/L, holding days, RSI, EMA9/21, Volume Ratio, swing score/grade/status, jarak ke SL/TP user, catatan.

**9 Action tersedia:**

| Action | Arti |
|---|---|
| `STRONG_HOLD` | Posisi sangat kuat, pertahankan |
| `HOLD` | Pertahankan posisi |
| `WATCH` | Pantau ketat, waspadai perubahan |
| `TIGHTEN_STOP_LOSS` | Pindahkan SL lebih ketat untuk protect profit |
| `TAKE_PROFIT_PARTIAL` | Ambil sebagian profit |
| `TAKE_PROFIT` | Ambil semua profit |
| `CUT_LOSS` | Potong rugi segera |
| `EXIT` | Keluar dari posisi (alasan selain loss) |
| `INSUFFICIENT_DATA` | Data tidak cukup untuk analisis |

**Output JSON:**
```json
{
  "action": "HOLD",
  "confidence": "HIGH | MEDIUM | LOW",
  "summary": "Ringkasan kondisi posisi...",
  "reason": "Alasan rekomendasi...",
  "risk": "Risiko utama...",
  "suggested_action": "Langkah konkret yang disarankan...",
  "suggested_sl": 9500,
  "suggested_tp": 11000
}
```

### 11.2 Portfolio-Level (`analyze_portfolio`)

Dijalankan saat user klik **"Analisis Portfolio"**.

**Input:** Semua posisi enriched + portfolio summary (total invested, return, alokasi %).

**Output JSON:**
```json
{
  "portfolio_score": 72,
  "health_status": "GOOD | CAUTION | CRITICAL | INSUFFICIENT_DATA",
  "summary": "Ringkasan kondisi keseluruhan portfolio...",
  "actions": [
    { "symbol": "BBCA.JK", "action": "HOLD", "reason": "..." }
  ],
  "concentration_risk": "Deskripsi risiko konsentrasi...",
  "suggestions": ["Saran 1", "Saran 2"]
}
```

---

## 12. Manajemen Portfolio (CRUD)

### Tambah Posisi

**Required fields:**
```json
{
  "symbol": "BBCA.JK",
  "quantity_lots": 10,
  "avg_buy_price": 9500,
  "buy_date": "2026-08-15"
}
```

**Optional fields:**
```json
{
  "company_name": "Bank Central Asia",
  "target_price": 11000,
  "stop_loss_price": 8800,
  "notes": "Entry di support EMA21"
}
```

### P/L Formula (konvensi IDX)

```
shares         = lots × 100
invested       = shares × avg_buy_price
current_value  = shares × current_price
unrealized_pnl = current_value − invested
pnl_pct        = unrealized_pnl / invested × 100
```

### Enrichment Data

Setiap posisi yang di-fetch di-enrich dengan:
- Harga terkini dari Yahoo Finance (`fast_info.last_price`, delayed)
- Kalkulasi P/L lengkap
- Holding duration (hari)
- Jarak ke target price & stop loss (%)
- Price status: `"delayed"` atau `"unavailable"`
- Technical data dari scanner jika saham ada di universe (RSI, EMA, score, grade, status)

---

## 13. Backtesting Engine

File: `app/backtest/engine.py`

### 13.1 Cara Kerja

**Prinsip utama:** Zero look-ahead bias — saat evaluasi candle ke-`t`, hanya data candle `0` hingga `t` yang tersedia.

**Warmup:** 25 candle pertama dilewati untuk stabilisasi indikator.

**Per candle iteration:**
1. **Jika ada posisi aktif:** cek exit conditions
   - Low ≤ stop_loss → **LOSS** (exit di stop_loss)
   - High ≥ TP1 → **WIN** (exit di TP1)
   - days_held ≥ max_hold_days → **TIME EXIT** (exit di close)
2. **Jika tidak ada posisi:** evaluasi `evaluate_signal(df[:t+1])`
   - Jika READY + score ≥ min_score → buka posisi

**Position sizing:**
```
risk_per_share = entry_price − stop_loss
shares = floor(1,000,000 / risk_per_share / 100) × 100
(risiko Rp1 juta per trade = 1% dari modal simulasi Rp100 juta)
Minimum: 100 saham (1 lot)
```

### 13.2 Metrics (`backtest/metrics.py`)

| Metric | Formula | Keterangan |
|---|---|---|
| `win_rate` | wins / total × 100 | % trade yang profit |
| `profit_factor` | gross_profit / gross_loss | Rasio total profit vs total loss |
| `expectancy` | (win% × avg_win_R) − (loss% × 1.0) | Ekspektasi per trade dalam R |
| `avg_r` | sum(R-multiples) / total | Rata-rata R-multiple per trade |
| `max_drawdown` | max((peak − equity) / peak) × 100 | Max drawdown dari puncak equity (%) |
| `equity_curve` | Array [{trade, equity, date}] | Data untuk grafik equity |

**Breakdown per setup:** PULLBACK dan BREAKOUT dihitung secara terpisah.

---

## 14. REST API Endpoints

### Market & Scanner

| Method | URL | Deskripsi |
|---|---|---|
| `POST` | `/api/update-data` | Download market data + run scanner (background) |
| `POST` | `/api/run-scanner` | Scan ulang tanpa download (background) |
| `GET` | `/api/status` | Cek status proses background |
| `GET` | `/api/stock-data/{symbol}` | Data lengkap satu saham (JSON) |

### AI

| Method | URL | Deskripsi |
|---|---|---|
| `GET` | `/api/ai-analysis/{symbol}` | AI analysis + berita (async, Gemini) |
| `GET` | `/api/ai-status` | Cek konfigurasi Gemini API |

### Portfolio

| Method | URL | Deskripsi |
|---|---|---|
| `GET` | `/api/portfolio` | Semua posisi aktif + P/L terkini |
| `GET` | `/api/portfolio/summary` | Summary portfolio (tanpa holdings) |
| `POST` | `/api/portfolio` | Tambah posisi baru |
| `GET` | `/api/portfolio/{id}` | Detail satu posisi + enrichment |
| `PUT` | `/api/portfolio/{id}` | Update posisi (partial update) |
| `DELETE` | `/api/portfolio/{id}` | Hapus posisi (soft delete) |
| `POST` | `/api/portfolio/ai-analysis` | AI analysis seluruh portfolio |
| `POST` | `/api/portfolio/{id}/ai-analysis` | AI analysis satu posisi |

### Debug

| Method | URL | Deskripsi |
|---|---|---|
| `GET` | `/debug/market-data/{symbol}` | Audit semua sumber harga untuk satu saham |

---

## 15. Alur Kerja End-to-End

### Skenario 1: Pagi hari, cari saham untuk trading

```
1. Buka http://localhost:8000
2. Klik "Update Market Data"
   → Download ~959 saham dari Yahoo Finance (50 per batch)
   → Hitung semua indikator teknikal
   → Jalankan screener + signal engine
   → Simpan hasil ke DB
3. Dashboard menampilkan "TOP READY SIGNALS"
4. Klik salah satu saham (e.g., BBCA.JK) → /stock/BBCA.JK
   → Chart, Entry/SL/TP, why signals
   → AI Analysis otomatis dimuat:
      - Ambil berita BBCA 3 hari terakhir
      - Gemini analisis + kutip berita nyata
5. Keputusan: BUY? HOLD? Tidak jadi masuk?
```

### Skenario 2: Pantau portfolio yang dimiliki

```
1. Buka /portfolio
   → Semua posisi + P/L realtime (delayed Yahoo Finance)
2. Klik posisi yang mau dipantau → /portfolio/3
   → P/L, holding days, technical signal terkini
3. Klik "Analisis AI Posisi Ini"
   → Gemini: HOLD? CUT_LOSS? TAKE_PROFIT_PARTIAL?
4. Klik "Analisis Portfolio"
   → Portfolio score, health status, rekomendasi per posisi
```

### Skenario 3: Validasi strategi via backtest

```
1. Buka /backtest
2. Pilih: symbol=TOP_READY, setup=PULLBACK, min_score=75, max_hold=5
3. Lihat: win rate, profit factor, equity curve, per-trade breakdown
4. Bandingkan PULLBACK vs BREAKOUT performance history
```

---

## 16. Struktur Folder

```
AsykarDayTrade/
├── run.py                      # Entry point (uvicorn + hot reload)
├── .env                        # Konfigurasi environment
├── .env.example                # Contoh konfigurasi
├── data/
│   └── idx_symbols.csv         # Universe saham IDX (~959 ticker)
├── logs/
│   └── app.log                 # Log aplikasi
├── requirements.txt
└── app/
    ├── config.py               # Load .env → konfigurasi global
    ├── main.py                 # FastAPI app + semua routes & endpoints
    ├── database/
    │   ├── connection.py       # SQLAlchemy engine (SQLite)
    │   ├── models.py           # ORM models (5 tabel)
    │   └── repositories.py     # CRUD functions
    ├── services/
    │   ├── market_data.py           # Download batch OHLCV (yfinance)
    │   ├── scanner_service.py       # Orchestrate screener + signal + ranking
    │   ├── ai_analyst.py            # AI saham individual (Gemini + Google News RSS)
    │   ├── portfolio_service.py     # P/L calculation + enrichment
    │   └── portfolio_ai_analyst.py  # AI portfolio (Gemini)
    ├── strategy/
    │   ├── signal_engine.py         # Scoring engine utama (0-100)
    │   ├── pullback.py              # PULLBACK detection
    │   ├── breakout.py              # BREAKOUT detection
    │   ├── support_resistance.py    # S/R zones dari swing + EMA
    │   └── risk_management.py       # Entry, SL, TP, R/R berbasis ATR
    ├── indicators/
    │   ├── trend.py     # EMA9/21, MA20/50, ATR, Dist_EMA9%
    │   ├── momentum.py  # RSI14, Stochastic RSI (K, D)
    │   └── volume.py    # Volume MA20, Ratio, Estimated Value
    ├── backtest/
    │   ├── engine.py    # Simulasi candle-by-candle (no look-ahead bias)
    │   └── metrics.py   # Win rate, PF, expectancy, equity curve, setup breakdown
    ├── providers/
    │   ├── base.py      # Abstract MarketDataProvider
    │   └── yahoo.py     # YahooFinanceProvider (daily + intraday + quote)
    ├── scanner/
    │   ├── screener.py  # Filter minimum (RSI, Volume, Value, Price)
    │   └── ranking.py   # Rank candidates by score
    ├── templates/
    │   ├── base.html                # Layout dasar (navbar, footer)
    │   ├── index.html               # Dashboard + Top READY signals
    │   ├── screener.html            # Tabel semua kandidat screener
    │   ├── stock_detail.html        # Detail saham + chart + AI panel
    │   ├── portfolio.html           # Portfolio management + P/L
    │   ├── portfolio_detail.html    # Detail satu posisi
    │   ├── backtest.html            # Backtest interface
    │   └── debug_market_data.html   # Diagnostic harga
    └── static/          # CSS, JS, icons
```

---

## Catatan Penting untuk AI

> Hal-hal khusus yang perlu dipahami tentang desain sistem ini:

1. **`daily_prices.close` ≠ harga terkini.** Ini adalah penutupan sesi sebelumnya. Harga terkini (`current_price`) diambil via `fast_info.last_price` hanya di halaman detail saham, untuk menghindari rate limiting saat scan 900+ saham.

2. **Scanner tidak fetch live price.** Screener menggunakan `daily_close` dari DB. Live quote hanya di-fetch per saham ketika user membuka halaman detail.

3. **Yahoo Finance delayed ~15-20 menit.** Bukan realtime. Cukup untuk swing/day trading IDX tapi tidak untuk scalping.

4. **Portfolio berdiri sendiri dari universe screener.** Tabel `portfolio_holdings` tidak ber-FK ke `symbols`, sehingga user bisa input saham yang belum ada di universe screener. Technical data di-enrichment jika saham tersebut ada di universe.

5. **AI portfolio dilarang mengklaim data yang tidak diberikan.** `PORTFOLIO_SYSTEM_PROMPT` secara eksplisit melarang AI mengakses data realtime, order book, atau fundamental yang tidak ada dalam prompt input.

6. **Backtest menggunakan IDR, modal simulasi Rp100 juta.** Sizing 1% risk per trade = Rp1 juta risiko per posisi.

7. **Timezone selalu Asia/Jakarta (WIB).** Semua timestamp UI, storage, dan debug menggunakan WIB. Data disimpan sebagai naive datetime (tanpa timezone) setelah konversi ke WIB.

8. **AI news context harus spesifik.** System prompt Gemini secara tegas melarang generalisasi sektor dan memaksa AI menyebut judul berita nyata yang diberikan dalam prompt.
