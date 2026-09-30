# 📑 LAPORAN AUDIT TEKNIS & ARSITEKTUR SISTEM
**Project:** IDX Day Trade Signal System (Local-First)  
**Dokumentasi:** Baseline Arsitektur & Kesiapan Pengembangan Intraday Day Trade  
**Tanggal Audit:** September 2026  
**Status Kode:** Freeze (Hanya Audit & Dokumentasi)

---

## 1. ARSITEKTUR APLIKASI

### Framework & Teknologi
* **Backend:** **Python 3.9+** menggunakan **FastAPI** (`v0.128.8`), dijalankan via ASGI Server **Uvicorn** (`v0.39.0`) dengan reload process (`StatReload`).
* **Database & ORM:** **SQLite** lokal via **SQLAlchemy 2.0**.
* **Frontend:** Server-Side Rendering (SSR) menggunakan **Jinja2 Templates**, komponen UI **Bootstrap 5 (Dark Mode)**, dan chart candlestick interaktif menggunakan **TradingView Lightweight Charts** via CDN.
* **HTTP Client & AI:** **`httpx`** (asynchronous) untuk integrasi Google Gemini REST API.

### File Utama & Struktur Direktori
* `run.py`: Entrypoint launcher aplikasi. Memastikan folder `data/`, `logs/`, `app/static/` ada, lalu menjalankan server Uvicorn pada host `0.0.0.0` port `8000`.
* `app/main.py`: Routing utama FastAPI. Menyediakan halaman HTML (`/`, `/screener`, `/stock/{symbol}`, `/backtest`, `/debug/market-data/{symbol}`) dan endpoint REST API (`/api/update-data`, `/api/run-scanner`, `/api/status`, `/api/stock-data/{symbol}`, `/api/ai-analysis/{symbol}`, `/api/ai-status`).
* `app/config.py`: Sentralisasi konfigurasi environment (`.env`), parameter threshold screener, rasio Risk/Reward, formula scoring, dan konfigurasi AI.
* `app/services/scanner_service.py`: Orchestrator scanning pasar (memuat data DB lokal, kalkulasi indikator, memanggil signal engine, dan menyusun ranking).
* `app/services/market_data.py`: Service sinkronisasi data batch dari Yahoo Finance ke database SQLite lokal.
* `app/services/ai_analyst.py`: Service client Google Gemini API untuk menghasilkan ringkasan naratif, AI Confidence Score, dan evaluasi sentimen.
* `app/strategy/signal_engine.py`: Core rule engine evaluasi sinyal teknikal dan sistem penilaian skor (0–100).
* `app/database/models.py` & `repositories.py`: Definisi skema tabel database dan fungsi query/upsert data.

### Penyimpanan Data (Database)
* File database lokal tersimpan di `data/stock_signal.db`.
* Terkonfigurasi fallback dinamis ke `/tmp/stock_signal.db` jika environment mendeteksi serverless deployment (Vercel).

### Cara Menjalankan & Model Proses
* **Menjalankan aplikasi:**
  ```bash
  source .venv/bin/activate
  python run.py
  ```
* **Model Proses:** Single-process event-loop (asynchronous FastAPI). Proses komputasi/download panjang ditangani melalui `fastapi.BackgroundTasks` di thread latar belakang sehingga UI web tetap responsif.

---

## 2. DATA MARKET

### Sumber & Karakteristik Data
* **Penyedia Data:** **Yahoo Finance** melalui library Python `yfinance`.
* **Universe Saham:** Di-load dari `data/idx_symbols.csv` berisi **625 emiten saham Bursa Efek Indonesia (IDX)** dengan akhiran `.JK` (contoh: `BBRI.JK`).
* **Sifat Data:** 
  * **Historical Data:** Tersimpan di database SQLite lokal hingga 250 hari bursa terakhir (Daily OHLCV).
  * **Live Quote Data:** Diambil langsung (*on-demand*) melalui `yfinance.Ticker(symbol).fast_info` ketika pengguna membuka halaman detail saham (`/stock/{symbol}`).
* **Delay Data:** Yahoo Finance IDX memiliki **delay sekitar 15–20 menit**. Data intraday berupa aggregated bar candle, bukan feed tick-by-tick real-time.

### Timeframe yang Tersedia vs yang Digunakan
* **Tersimpan di Database Saat Ini:** **HANYA Daily (`1d`)**.
* **Ketersediaan API `yfinance`:** Secara teknis mendukung `1m` (maks 7 hari), `5m`, `15m`, `30m`, `1h`, `1d`.
* **Kondisi Kode Saat Ini:**
  * Provider `app/providers/yahoo.py` sudah memiliki fungsi `get_intraday_data(symbol, interval="15m", period="5d")`.
  * Tabel database `intraday_prices` **sudah didefinisikan**, tetapi fungsi batch download `update_market_data()` **sama sekali belum mendownload atau mengisi data intraday ke DB**. Fungsi intraday saat ini hanya dipakai di endpoint audit debug `/debug/market-data/{symbol}`.

### Format Waktu & Timezone
* Waktu bursa dikonversi ke **WIB (`Asia/Jakarta`)**.
* Data candle harian disimpan di SQLite sebagai `datetime` naive pada jam `00:00:00` tanggal kalender lokal untuk menghindari pergeseran tanggal UTC shift.

---

## 3. STRATEGI / RULE ENGINE SAAT INI

Rule engine dieksekusi di `app/strategy/signal_engine.py` untuk menghasilkan skor (0–100), grade sinyal, jenis setup, dan level trading.

### 1. Base Screener Filter (`app/scanner/screener.py`)
Saham harus lolos kriteria minimum berikut pada candle harian terakhir:
* **Price:** $\text{Close} \ge 200$ Rupiah (menghindari saham tidur/gocap).
* **RSI (14):** $50.0 \le \text{RSI} \le 70.0$ (momentum sehat tanpa overbought).
* **Volume:** $\ge 1.000.000$ lembar saham.
* **Estimated Value:** $\text{Close} \times \text{Volume} \ge \text{Rp } 10.000.000.000$ (Rp 10 Miliar).
* **Volume Momentum:** $\text{Volume Ratio} \ge 1.0$ ($\text{Volume} \ge \text{SMA20 Volume}$).

### 2. Scoring System (Maksimal 100 Poin)
Skor dihitung dari akumulasi 5 pilar teknikal berikut:

#### A. Trend Score (Maksimal 25 Poin)
* $\text{Price} > \text{EMA9}$: **+8 poin**
* $\text{EMA9} > \text{EMA21}$: **+8 poin**
* $\text{EMA21 Slope} > 0$: **+5 poin**
* $\text{Price} > \text{MA20} > \text{MA50}$: **+4 poin**

#### B. Momentum Score (Maksimal 20 Poin)
* $50.0 \le \text{RSI14} \le 70.0$: **+10 poin**
* $55.0 < \text{RSI14} \le 72.0$: **+5 poin**
* Stochastic RSI Bullish Crossover ($\text{K} > \text{D}$ dan $\text{K} \ge 20$): **+5 poin**

#### C. Liquidity Score (Maksimal 20 Poin)
* $\text{Estimated Value} \ge \text{Rp } 10\text{ Miliar}$: **+7 poin**
* $\text{Volume} \ge 1.000.000\text{ lembar}$: **+5 poin**
* $\text{Volume Ratio} \ge 1.5\text{x}$: **+8 poin** (jika $1.0 \le \text{Ratio} < 1.5$, diberi **+4 poin**)

#### D. Setup Score (Maksimal 25 Poin)
* **Setup PULLBACK** (`app/strategy/pullback.py`):
  * Kondisi: Trend bullish ($\text{Close} \ge 0.985 \times \text{EMA9}$ dan $\text{EMA9} \ge 0.99 \times \text{EMA21}$), harga di atas support, jarak ke EMA9 $\le 3\%$: **+15 poin**.
  * Konfirmasi support bertahan: **+5 poin**.
  * RSI 45–68 (momentum pulih): **+5 poin**.
* **Setup BREAKOUT** (`app/strategy/breakout.py`):
  * Kondisi: Harga mendekati resistance/swing high terakhir ($\ge 98\%$), didukung volume expansion ($\ge 1.4\text{x}$) atau konsolidasi 5 bar ($\le 8\%$): **+15 poin**.
  * Konfirmasi volume expansion: **+5 poin**.
  * Konfirmasi konsolidasi ketat: **+5 poin**.

#### E. Risk / Reward Score (Maksimal 10 Poin)
* $\text{Risk/Reward} \ge 2.0$: **+10 poin**
* $1.5 \le \text{Risk/Reward} < 2.0$: **+5 poin**
* $\text{Risk/Reward} < 1.5$: **0 poin**

#### F. Penalti (Pengurangan Poin)
* $\text{RSI} > 75$: **-10 poin** (overbought ekstrim).
* $\text{Distance from EMA9} > 3\%$: **-10 poin** (harga mulai extended).
* $\text{Distance from EMA9} > 5\%$: **-20 poin** (harga sangat rawan pullback tajam).
* $\text{Value} < 5\text{ Miliar}$ atau $\text{Volume} < 500.000$: **-20 poin**.

### 3. Klasifikasi Grade & Status
* **Grade:**
  * **`A+`**: Skor $\ge 85$
  * **`A`**: Skor $75 - 84$
  * **`WATCH`**: Skor $65 - 74$
  * **`LOW QUALITY`**: Skor $50 - 64$
  * **`NO TRADE`**: Skor $< 50$
* **Status Eksekusi:**
  * **`READY`**: Setup terkonfirmasi, skor $\ge 75$ (atau $\ge 70$ di ranking filter), tidak over-extended ($\text{Dist EMA9} \le 4\%-5\%$), dan $\text{RR} \ge 1.5$.
  * **`WAIT_PULLBACK`**: Harga extended $> 5\%$ dari EMA9, menunggu retracement ke dynamic support.
  * **`WAIT_BREAKOUT`**: Berada di resistance tetapi belum menembus dengan volume valid.
  * **`NO_TRADE`**: Rasio Risk/Reward $< 1.5$ atau skor buruk.

### 4. Trade Level Calculation (`app/strategy/risk_management.py`)
* **Entry Zone:**
  * Pullback: Rentang antara $\text{EMA21}$ / $\text{EMA9} \times 0.995$ hingga $\text{Close} \times 1.005$.
  * Breakout: $\text{Close} \times 0.995$ s/d $\text{Close} \times 1.005$.
* **Stop Loss (SL):**
  * Pullback: $\min(\text{Swing Low} \times 0.99, \text{Support Low} \times 0.99, \text{Entry Low} - 1.2 \times \text{ATR})$.
  * Breakout: $\min(\text{Entry Low} \times 0.97, \text{Entry Low} - 1.5 \times \text{ATR})$.
* **Take Profit:**
  * $\text{TP1} = \text{Entry High} + (1.5 \times \text{Risk})$.
  * $\text{TP2} = \text{Entry High} + (2.0 \text{ s/d } 2.2 \times \text{Risk})$.
  * Di mana $\text{Risk} = \text{Entry High} - \text{Stop Loss}$.

---

## 4. SCREENING PIPELINE

Alur eksekusi saat scanner dijalankan (`app/services/scanner_service.py`):

```
625 Saham (idx_symbols.csv)
  │
  ▼
Load Dataframe (250 Daily Candles per saham dari SQLite)
  │
  ▼
Base Screener Filter (screener.run_base_screener)
  │
  ▼
Signal Engine Evaluation (signal_engine.evaluate_signal)
  ├─ Hitung Skor (0-100), Grade (A+, A, WATCH, dll)
  └─ Tentukan Status (READY, WAIT_PULLBACK, dll)
  │
  ▼
Simpan ke Tabel Database `signals`
  │
  ▼
Pembagian Subset:
  ├─ all_results: Seluruh 625 saham
  ├─ passed_results: Saham yang lolos base screener
  └─ ready_results: Saham dengan status == "READY" dan score >= 70
  │
  ▼
Ranking (ranking.rank_candidates)
  └─ Disortir menurun berdasarkan: (Score, Risk_Reward)
  │
  ▼
UI Dashboard Top Candidates (Menampilkan daftar `ready_candidates`)
  │
  ▼
AI Analysis (Dieksekusi HANYA saat user membuka /stock/{symbol})
```

* **Berapa kandidat yang dikirim ke AI?**
  **TIDAK ADA batch sending ke AI**. AI **tidak** memproses 625 saham atau Top 10 sekaligus. Pemanggilan AI bersifat **on-demand (1 saham per request)** via AJAX saat pengguna mengklik halaman detail saham tertentu.

---

## 5. AI ANALYST

### Spesifikasi Teknis
* **Model:** **Google Gemini API** (`gemini-2.5-flash`).
* **Apakah menggunakan Ollama?** **TIDAK**. Kode Ollama telah sepenuhnya diganti dengan REST API resmi Google AI Studio (Free Tier) yang berjalan langsung dari dalam backend Python via library `httpx`.
* **Pemanggilan:** Asynchronous endpoint `GET /api/ai-analysis/{symbol}` yang dipanggil dari script frontend di `stock_detail.html` setelah DOM halaman selesai dimuat (*lazy loading*).

### Input & Context yang Dikirim ke AI (`app/services/ai_analyst.py`)
Prompt yang dikirim berisi rekap data teknikal saham:
1. Identitas: Ticker, Nama Emiten, Sektor, Tanggal Candle Terakhir.
2. Parameter Teknikal: Nilai Close, RSI14, EMA9, EMA21, Volume Ratio 20d, Jarak harga ke EMA9 (%), Nilai Transaksi Harian (Rp Miliar).
3. Hasil Rule Engine: Setup terdeteksi, Grade, Skor Sistem, Status, Entry Zone, SL, TP1, TP2, Rasio Risk/Reward.
4. Checklist Sistem: Poin `why_this_stock` (alasan positif) dan `why_not_ready` (catatan kelemahan setup).

### Skema Output JSON
Gemini diwajibkan mengembalikan JSON murni (`responseMimeType: "application/json"`):
```json
{
  "ai_summary": "Ringkasan kondisi saham dalam 2-3 kalimat...",
  "ai_confidence": 75,
  "ai_recommendation": "BUY",
  "ai_recommendation_reason": "Alasan utama rekomendasi...",
  "ai_risks": ["risiko 1", "risiko 2"],
  "ai_opportunities": ["peluang 1", "peluang 2"],
  "ai_market_context": "Komentar kondisi sektor / IHSG..."
}
```

### Karakteristik & Limitasi AI Saat Ini
* **Peran AI dalam Ranking:** AI **TIDAK melakukan ranking ulang** terhadap Top 10. AI bertindak murni sebagai **analis penjelas (naratif & second-opinion)** untuk saham yang dibuka trader.
* **Integrasi Berita (News):** **BELUM ADA**. AI saat ini hanya mengevaluasi data teknikal yang diberikan dalam prompt.
* **Perhitungan Confidence:** Nilai integer (0–100) ditentukan secara probabilistik oleh LLM berdasarkan konsistensi sinyal teknikal di dalam prompt.

---

## 6. CURRENT TIMEFRAME & KLASIFIKASI STRATEGI

### Timeframe Aktual
* **Screener:** **DAILY (1D)**
* **RSI:** **DAILY (14 Hari)**
* **EMA:** **DAILY (EMA 9 Hari, EMA 21 Hari)**
* **Volume & Volume Ratio:** **DAILY (Volume vs SMA 20 Hari)**
* **Support / Resistance:** **DAILY (Swing High/Low 10 Hari)**
* **Entry, Stop Loss, Take Profit:** **Dihitung dari Daily Candle**
* **AI Analysis:** **Mengevaluasi rekapitulasi indikator Daily**

### Klasifikasi Strategi Saat Ini
> **Klasifikasi Sebenarnya:** **B. Swing Trading (Short-Term Swing / Position 1–5 Hari) dengan elemen Momentum Trading.**

**Alasan Berdasarkan Kode (Bukan Asumsi):**
1. Di file `app/backtest/engine.py:128`, backtest dijalankan dengan parameter default `max_hold_days = 5`.
2. Semua level SL dan TP memiliki jarak rata-rata 3% s/d 8% yang dihitung berdasarkan swing candle harian (Daily High/Low/ATR), bukan pergerakan tick/menit intraday.
3. Kode screener tidak pernah membaca pergerakan harga menit-ke-menit pada hari bursa berjalan untuk memutuskan sinyal masuk.

---

## 7. MARKET SESSION & VALIDITAS SINYAL

* **Pemahaman Jam Pasar:**
  * Aplikasi saat ini **hanya memiliki 1 fungsi pengecekan kasar** di `app/main.py:273`:
    `is_trading_hours = (weekday < 5) and ((9, 0) <= (hour, minute) <= (16, 0))`
  * Aplikasi **belum memahami**:
    * Sesi Pre-Opening (08:45–08:59)
    * Sesi 1 (09:00–12:00, atau 11:30 hari Jumat)
    * Istirahat Siang / Lunch Break (12:00–13:30)
    * Sesi 2 (13:30–15:49)
    * Pre-Closing & Post-Trading (15:50–16:15)
* **Masa Berlaku Sinyal:**
  * **Belum memiliki konsep "Sinyal hanya valid untuk hari ini / sesi ini"**.
  * Sinyal yang disimpan di tabel `signals` bersifat statis sampai pengguna menekan tombol *Update Market Data* atau *Run Screener* berikutnya.

---

## 8. PRICE LIVE VS DAILY CLOSE

| Parameter | Sumber Data | Digunakan Untuk |
| :--- | :--- | :--- |
| **Daily Close** | SQLite tabel `daily_prices` (`close` sesi bursa kemarin yang sudah selesai). | **Dasar 100% kalkulasi rule engine**: RSI, EMA, Support/Resistance, Entry Zone, SL, TP, dan Scoring. |
| **Current / Live Price** | `yf.Ticker.fast_info.last_price` (delay 15–20 menit). | **Hanya ditampilkan sebagai teks widget** di UI detail saham dan perbandingan % selisih harga hari ini. |
| **Intraday Candle Price** | `yf.Ticker.history(interval="15m")`. | **Hanya ditampilkan di tabel audit halaman debug**, tidak terhubung ke engine sinyal. |

> **Temuan Kunci:** Entry Zone, Stop Loss, dan Take Profit saat ini **100% dihitung menggunakan Daily Close**, bukan harga intraday live.

---

## 9. INTRADAY CAPABILITY AUDIT

| Aspek | Sudah Tersedia? | Kondisi / Catatan |
| :--- | :---: | :--- |
| Skema DB `IntradayPrice` | ✅ Ada | Tabel SQLite sudah memiliki kolom `timestamp`, `interval`, `open`, `high`, `low`, `close`, `volume`. |
| Repo Query Intraday | ✅ Ada | `save_intraday_prices` dan `get_recent_intraday_prices` sudah tersedia di `repositories.py`. |
| Provider Fetch Intraday | ✅ Ada | `YahooFinanceProvider.get_intraday_data()` sudah tersedia. |
| Batch Intraday Downloader | ❌ Belum | `update_market_data` hanya mendownload data daily (`1d`). |
| Intraday Indicator Engine | ❌ Belum | Fungsi indikator di `app/indicators/` hanya menerima dataframe harian. VWAP harian belum ada. |
| Timeframe Menit (5m / 15m) | ❌ Belum | Belum terintegrasi ke engine sinyal. |
| Session State Machine | ❌ Belum | Belum ada logic pemantau pergantian Sesi 1, Istirahat, Sesi 2, dan Auto-Exit sebelum tutup bursa. |

---

## 10. REKOMENDASI ARSITEKTUR ENGINE INTRADAY DAY TRADE

Untuk mengubah sistem menjadi **Day Trading sejati** tanpa merusak arsitektur yang ada, berikut arsitektur modular yang disarankan:

```
┌─────────────────────────────────────────────────────────────┐
│ LAYER 1: PRE-MARKET DAILY SCANNER (08:00 - 08:50 WIB)       │
│ • Menjalankan screening dari 625 saham harian.              │
│ • Memfilter Daily Trend: EMA9 > EMA21, RSI 50-70, Vol > 10B.│
│ • Output: "Top 20 Intraday Watchlist" (fokus kandidat).     │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ LAYER 2: INTRADAY STREAMER & ENGINE (09:00 - 15:30 WIB)     │
│ • Polling interval 5m / 15m HANYA untuk 20 saham watchlist. │
│ • Menghitung Intraday Indicators:                           │
│   - VWAP (Volume Weighted Average Price)                    │
│   - Opening Range Breakout (ORB 15-Menit Pertama)           │
│   - 5m / 15m EMA9 Pullback                                  │
│ • Entry Rule: Harga menembus High 15m pertama + Volume Surge│
│   ATAU Pullback menyentuh VWAP / EMA9 intraday.             │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ LAYER 3: LIVE PRICE & RISK GATE                             │
│ • Stop Loss Intraday: Di bawah Low candle 15m atau VWAP.    │
│ • Invalidation Check: Jika harga jatuh tembus SL sebelum    │
│   tersentuh Entry, status berubah menjadi CANCELLED/INVALID.│
│ • Auto-close Rule: Pukul 15:45 WIB semua posisi ditutup     │
│   (tidak menginapkan posisi / strictly day trade).          │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ LAYER 4: AI INTRADAY CONFIRMATION (Gemini 2.5 Flash)        │
│ • Menganalisis keselarasan Trend Daily + Setup Intraday.     │
│ • Memberikan rekomendasi eksekusi cepat (BUY NOW / CANCEL). │
└─────────────────────────────────────────────────────────────┘
```

---

## 11. TABEL KEBUTUHAN DATA DAY TRADE

| Data | Sudah Tersedia? | Sumber Saat Ini | Timeframe Dibutuhkan | Bisa Dipakai untuk Intraday? | Catatan Kritis |
| :--- | :---: | :--- | :--- | :---: | :--- |
| **Daily Trend Context** | ✅ Ya | SQLite (`daily_prices`) | Daily (`1d`) | ✅ Ya (Sebagai Trend Filter) | Sudah optimal untuk filter arah tren utama. |
| **Intraday Candles (15m/5m)** | ⚠️ Parsial | Yahoo Finance (`yf.history`) | `5m`, `15m` | ✅ Ya (Dengan Polling Batch) | API yfinance mendukung, tapi perlu scheduler download khusus untuk 20–30 saham terpilih. |
| **VWAP (Volume Weighted Avg)** | ❌ Belum | Harus dihitung dari 5m/15m bar | Intraday (reset per hari) | ❌ Belum dihitung | Indikator wajib Day Trader institusi/ritel. Rumus: $\frac{\sum (\text{Typical Price} \times \text{Volume})}{\sum \text{Volume}}$. |
| **Live Tick-by-Tick Price** | ❌ Tidak | - | Real-time (0s delay) | ⚠️ Terbatas | Yahoo Finance delay 15 menit. Untuk scalping detik butuh broker feed (misal IPOT/Mirae/Goquant API), tetapi untuk **15m swing day trade**, data Yahoo masih dapat digunakan sebagai prototipe. |
| **Opening Range (ORB)** | ❌ Belum | Harus dihitung dari candle 09:00–09:15 | `15m` bar pertama | ❌ Belum ada logic | High & Low 15 menit pertama pembukaan bursa. |
| **Broker Summary / Bandarmologi** | ❌ Tidak | Tidak tersedia di Yahoo Finance | EOD / Intraday | ❌ Tidak | Fitur lokal IDX yang tidak disediakan oleh feed data internasional. |

---

## 12. DAFTAR FILE YANG AKAN TERLIBAT UNTUK INTRADAY ENGINE

Jika pengembangan fitur Intraday Day Trade dimulai, berikut adalah file-file yang akan dimodifikasi atau dibuatkan modul baru:

1. **Konfigurasi & Parameter:**
   * `app/config.py`: Tambahkan konfigurasi jam buka/tutup sesi bursa, timeframe intraday (`5m`, `15m`), dan limit watchlist.
2. **Provider & Sinkronisasi:**
   * `app/providers/yahoo.py`: Tambahkan helper pengambilan batch intraday candles khusus watchlist.
   * `app/services/market_data.py`: Tambahkan fungsi `update_intraday_watchlist_data()`.
3. **Indikator Baru:**
   * `app/indicators/intraday.py` *(Modul Baru)*: Kalkulasi VWAP harian, Opening Range (High/Low 15m pertama), dan Momentum Intraday.
4. **Strategy & Sinyal Intraday:**
   * `app/strategy/intraday_engine.py` *(Modul Baru)*: Rule engine intraday (ORB Breakout, VWAP Rebound, Micro-pullback 5m).
   * `app/strategy/risk_management.py`: Adaptasi perhitungan SL/TP berbasis level intraday (bukan daily ATR).
5. **Database Repositories:**
   * `app/database/repositories.py`: Implementasi fungsi query/upsert aktif ke tabel `IntradayPrice`.
6. **API & UI Controller:**
   * `app/main.py`: Tambahkan route `/api/intraday-signals` dan scheduler polling sesi aktif.
   * `app/templates/stock_detail.html` & `base.html`: Tambahkan switch timeframe (1D / 15m / 5m) pada TradingView chart.
