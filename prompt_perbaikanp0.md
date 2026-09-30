# P0 — SIGNAL INTEGRITY + TRADING WORKFLOW UI

## 1. Tujuan

Lakukan enhancement P0 pada aplikasi **AsykarDayTrade** dengan dua fokus utama:

1. **Merapikan dan menghilangkan ambiguity pada Signal Engine**
2. **Mendesain ulang UI agar user langsung memahami workflow trading dari awal sampai keputusan akhir**

P0 TIDAK bertujuan mengubah strategi trading utama, formula indikator, atau menambah indikator baru.

Fokus utama:

> User harus bisa membuka aplikasi dan langsung memahami:
>
> **Apa yang sedang terjadi → saham mana yang menarik → kenapa menarik → apakah sekarang waktunya entry → berapa entry/SL/TP → apakah signal masih valid → apa tindakan berikutnya.**

---

# 2. Kondisi Sistem Saat Ini

Aplikasi saat ini memiliki:

* Technical indicators
* Screener
* Signal Engine score 0–100
* Grade A+/A/WATCH/LOW QUALITY/NO TRADE
* Setup PULLBACK / BREAKOUT
* Status READY / WAIT_PULLBACK / WAIT_BREAKOUT / WATCH / NO_TRADE
* Entry Zone
* Stop Loss
* TP1 / TP2
* Risk/Reward
* AI Analysis
* Portfolio
* Backtest

Jangan menghapus fitur existing.

Pertahankan compatibility dengan API dan template existing sebisa mungkin.

---

# 3. MASALAH YANG HARUS DISELESAIKAN

## 3.1 Score dan READY memiliki ambiguity

Saat ini dokumentasi memiliki:

```text
MIN_SIGNAL_SCORE = 75
```

Tetapi terdapat referensi bahwa ready candidates menggunakan score >= 70.

Hilangkan ambiguity tersebut.

Gunakan:

```text
MIN_SIGNAL_SCORE = 75
```

sebagai SINGLE SOURCE OF TRUTH.

Jangan hardcode angka 70 di tempat lain.

Semua logic yang menentukan READY harus menggunakan konfigurasi yang sama.

---

# 4. DEFINISI FINAL SIGNAL

Gunakan struktur konsep berikut:

```text
SIGNAL SCORE
    ↓
SIGNAL QUALITY
    ↓
SETUP VALIDITY
    ↓
RISK VALIDITY
    ↓
ENTRY VALIDITY
    ↓
FINAL STATUS
```

Signal Score adalah **quality score**, BUKAN probability.

Jangan tampilkan:

```text
82% probability
```

jika angka 82 berasal dari scoring engine.

Tampilkan:

```text
Signal Score
82 / 100
```

---

# 5. DEFINISI GRADE

Pertahankan:

| Score | Grade       |
| ----: | ----------- |
| >= 85 | A+          |
| >= 75 | A           |
| >= 65 | WATCH       |
| >= 50 | LOW QUALITY |
|  < 50 | NO TRADE    |

Grade menunjukkan:

> Kualitas setup berdasarkan scoring engine.

Grade TIDAK otomatis berarti BUY.

Contoh:

```text
Grade A
Status WAIT_PULLBACK
```

adalah valid.

Artinya kualitas setup bagus tetapi entry belum valid.

---

# 6. DEFINISI STATUS

Gunakan status sebagai ACTION STATE.

## READY

Semua kondisi utama terpenuhi:

```text
setup valid
risk/reward valid
score >= MIN_SIGNAL_SCORE
entry masih valid
```

Meaning:

> Setup sudah memenuhi syarat untuk dipertimbangkan sebagai entry.

Jangan mengartikan READY sebagai jaminan profit.

---

## WAIT_PULLBACK

Setup pullback valid tetapi harga belum berada pada entry condition.

UI harus menjelaskan:

```text
WAIT PULLBACK

Why:
Harga belum masuk area pullback yang ideal.

Action:
Tunggu harga masuk Entry Zone.
```

---

## WAIT_BREAKOUT

Setup breakout valid tetapi breakout belum terkonfirmasi.

UI:

```text
WAIT BREAKOUT

Why:
Harga mendekati resistance tetapi breakout belum confirmed.

Action:
Tunggu breakout + volume confirmation.
```

---

## WATCH

Score cukup menarik tetapi belum memenuhi seluruh requirement READY.

UI:

```text
WATCH

Why:
Setup cukup menarik tetapi belum memenuhi semua
kondisi entry.

Action:
Pantau perubahan signal.
```

---

## NO_TRADE

Tidak memenuhi syarat untuk entry.

UI wajib memberikan alasan utama.

Contoh:

```text
NO TRADE

Reason:
Risk/Reward hanya 1.2
Minimum required: 1.5

Action:
Do not enter.
```

---

# 7. ENTRY VALIDITY

Tambahkan konsep baru:

```text
ENTRY_VALIDITY
```

Minimal memiliki:

```text
VALID
MISSED
EXTENDED
INVALID
UNKNOWN
```

## VALID

Harga masih berada dalam entry zone atau kondisi entry masih acceptable.

---

## MISSED

Harga sudah bergerak melewati entry zone sehingga entry ideal sudah terlewat.

Contoh:

```text
Entry Zone:
9,400 – 9,500

Current:
9,650

Status:
MISSED
```

UI:

```text
⚠️ ENTRY MISSED

Do not chase.

Wait for:
- pullback
- new setup
```

---

## EXTENDED

Harga terlalu jauh dari EMA/reference entry sehingga mengejar harga memiliki risk lebih tinggi.

Gunakan threshold yang konsisten dengan logic existing `Dist_EMA9`.

Jangan membuat threshold baru secara sembarangan.

---

## INVALID

Setup sudah tidak valid.

Contoh:

```text
Price broke below support
```

atau kondisi signal engine tidak lagi memenuhi setup.

---

## UNKNOWN

Tidak cukup data untuk menentukan entry validity.

---

# 8. SIGNAL FRESHNESS

Setiap signal harus memiliki timestamp.

Tambahkan konsep:

```text
signal_generated_at
```

dan hitung:

```text
signal_age
```

Contoh:

```text
Signal generated:
12 Sep 2026 09:15 WIB

Age:
2h 14m
```

Gunakan status:

```text
FRESH
AGING
STALE
```

Jangan menentukan threshold baru tanpa melihat struktur existing.

Threshold sebaiknya dibuat configurable.

Contoh konfigurasi:

```env
SIGNAL_FRESH_MINUTES=60
SIGNAL_AGING_MINUTES=180
```

Jika belum ada konfigurasi existing, implementasikan dengan default yang masuk akal dan configurable.

---

# 9. FINAL SIGNAL OBJECT

Buat satu struktur data yang menjadi sumber utama untuk frontend.

Contoh:

```json
{
  "symbol": "BBCA.JK",
  "score": 84,
  "grade": "A",
  "setup": "PULLBACK",
  "status": "READY",

  "entry_low": 9450,
  "entry_high": 9550,

  "stop_loss": 9200,
  "tp1": 10000,
  "tp2": 10500,

  "risk_reward": 2.0,

  "entry_validity": "VALID",
  "freshness": "FRESH",

  "signal_generated_at": "...",
  "signal_age_minutes": 35,

  "primary_reason": "...",
  "next_action": "CONSIDER_ENTRY"
}
```

Jangan memaksa frontend menghitung ulang business logic.

Backend harus menentukan state.

Frontend hanya menampilkan state.

---

# 10. NEXT ACTION

Tambahkan konsep:

```text
next_action
```

Contoh:

```text
READY + VALID
→ CONSIDER_ENTRY

WAIT_PULLBACK
→ WAIT_PULLBACK

WAIT_BREAKOUT
→ WAIT_BREAKOUT

WATCH
→ MONITOR

MISSED
→ DO_NOT_CHASE

EXTENDED
→ WAIT_REENTRY

NO_TRADE
→ DO_NOT_ENTER

STALE
→ RECHECK_SIGNAL
```

Tujuan utamanya:

> User tidak perlu menebak apa yang harus dilakukan setelah membaca signal.

---

# 11. UI WORKFLOW REDESIGN

UI harus mengikuti workflow trading manusia, bukan workflow internal backend.

Gunakan alur:

```text
1. MARKET
   ↓
2. FIND
   ↓
3. EVALUATE
   ↓
4. PLAN
   ↓
5. DECIDE
   ↓
6. MONITOR
```

---

# 12. DASHBOARD

Dashboard menjadi pusat workflow.

Urutan informasi:

## SECTION 1 — MARKET STATUS

Tampilkan:

```text
MARKET TODAY

Market:
OPEN / CLOSED

Market Data:
Updated XX minutes ago

Signal Scan:
Completed XX minutes ago
```

Jika market sedang closed:

```text
MARKET CLOSED

Last session:
12 Sep 2026

Signals shown below are based on latest available data.
```

---

# 13. DASHBOARD — WHAT SHOULD I DO?

Tambahkan section paling penting:

```text
WHAT SHOULD I DO?
```

Jangan langsung menampilkan puluhan saham.

Kelompokkan:

```text
🟢 READY TO CONSIDER
🟡 WAIT FOR SETUP
⚪ WATCH
🔴 NO TRADE
```

Contoh:

```text
READY TO CONSIDER

BBCA
A | 86
PULLBACK
Entry 9,450 – 9,550
SL 9,200
TP1 10,000
RR 2.0

[View Setup]
```

---

# 14. DASHBOARD — TOP SIGNALS

Jangan hanya sorting berdasarkan score.

Prioritaskan:

```text
READY
+
ENTRY VALID
+
FRESH
```

Kemudian ranking berdasarkan score.

Contoh:

```text
#1 BBCA
A+ 89
READY
🟢 FRESH

#2 BMRI
A 83
READY
🟢 FRESH

#3 BBRI
A 81
WAIT PULLBACK
🟡
```

Dengan demikian score tinggi yang belum actionable tidak mengalahkan setup yang benar-benar siap.

---

# 15. SCREENER UI

Screener harus membantu user menjawab:

> "Dari ratusan saham, mana yang perlu saya lihat?"

Tambahkan filter/action state.

Filter:

```text
ALL
READY
WAIT
WATCH
NO TRADE
```

Tambahkan filter:

```text
Entry Valid
Fresh Signal
PULLBACK
BREAKOUT
```

Kolom utama:

```text
Symbol
Price
Score
Grade
Setup
Status
Entry
SL
TP1
RR
Freshness
Next Action
```

Jangan membuat user membaca 15 indikator terlebih dahulu.

Indikator detail tetap tersedia di detail saham.

---

# 16. STOCK DETAIL UI

Halaman detail saham harus memiliki workflow yang sangat jelas.

Gunakan struktur:

```text
[HEADER]

BBCA
Bank Central Asia

A | 86
READY
🟢 FRESH

        ↓

[WHAT IS HAPPENING?]

[WHY?]

[TRADE PLAN]

[ENTRY STATUS]

[CHART]

[TECHNICAL DETAILS]

[AI ANALYSIS]
```

---

# 17. STOCK DETAIL — HEADER

Header harus langsung menjawab:

```text
BBCA

Signal:
READY

Grade:
A+

Score:
88 / 100

Setup:
PULLBACK

Signal:
🟢 FRESH
```

Jangan menyembunyikan status di bawah chart.

---

# 18. STOCK DETAIL — WHAT IS HAPPENING?

Tambahkan card:

```text
WHAT IS HAPPENING?

BBCA is showing a bullish pullback setup.

Price is near EMA9/EMA21 support
and the current setup still qualifies.

Signal is FRESH.
```

Bahasa harus berasal dari actual data.

Jangan membuat generic statement.

---

# 19. STOCK DETAIL — WHY?

Gunakan visual evidence.

Contoh:

```text
WHY THIS SIGNAL?

✓ Price above EMA9
✓ EMA9 above EMA21
✓ RSI 57
✓ Volume Ratio 1.8x
✓ Risk/Reward 2.1
✓ Pullback near support
```

Kemudian:

```text
⚠ Risk

Price is X% above EMA9.
```

Jangan hanya menampilkan score tanpa alasan.

---

# 20. STOCK DETAIL — TRADE PLAN

Buat satu card besar:

```text
TRADE PLAN

Entry Zone
Rp9,450 – Rp9,550

Stop Loss
Rp9,200

TP1
Rp10,000

TP2
Rp10,500

Risk / Reward
1 : 2.0
```

Gunakan visual horizontal flow:

```text
ENTRY
  ↓
SL / RISK
  ↓
TP1
  ↓
TP2
```

Jika entry invalid:

```text
⚠ ENTRY NO LONGER VALID
```

Jangan tetap menampilkan BUY/READY dengan visual hijau seolah-olah masih actionable.

---

# 21. STOCK DETAIL — NEXT ACTION

Ini wajib ada.

Contoh:

```text
NEXT ACTION

🟢 CONSIDER ENTRY

Price is inside the valid entry zone.

Suggested behavior:
Follow planned position sizing and stop loss.
```

Untuk WAIT:

```text
NEXT ACTION

🟡 WAIT FOR PULLBACK

Do not chase the current price.
```

Untuk MISSED:

```text
NEXT ACTION

⚠ DO NOT CHASE

Entry zone has already been passed.

Wait for a new setup.
```

---

# 22. AI ANALYSIS UI

AI jangan ditempatkan sebagai keputusan paling atas.

Urutan:

```text
SYSTEM SIGNAL
      ↓
TRADE PLAN
      ↓
AI CONTEXT
```

AI adalah decision-support layer, bukan pengganti Signal Engine.

Tampilkan:

```text
AI ANALYSIS

Recommendation:
BUY

Confidence:
65

Why:
...

News:
...

Risks:
...
```

Tetapi tetap tampilkan system state secara terpisah.

Jika:

```text
System:
READY

AI:
HOLD
```

Jangan menyembunyikan perbedaan tersebut.

Tampilkan:

```text
SYSTEM SIGNAL
READY

AI VIEW
HOLD

⚠ The technical system sees an actionable setup,
but AI identifies additional risk from recent context.
```

---

# 23. IMPORTANT — AI HARUS MENGHORMATI DATA

AI tidak boleh mengklaim:

* realtime price jika tidak diberikan
* order book
* broker flow
* fundamental
* data yang tidak ada di prompt

Pertahankan existing restriction.

AI juga tidak boleh mengubah:

```text
signal score
grade
entry
SL
TP
```

secara diam-diam.

Jika AI memiliki pandangan berbeda, tampilkan sebagai:

```text
AI VIEW
```

bukan overwrite system signal.

---

# 24. COLOR / VISUAL LANGUAGE

Gunakan warna berdasarkan ACTION STATE, bukan sekadar score.

```text
GREEN
READY / VALID

YELLOW
WAIT / WATCH / AGING

RED
NO TRADE / INVALID / STALE

NEUTRAL
INFORMATION
```

Jangan membuat:

```text
Score 85 = otomatis hijau
```

karena score tinggi belum tentu entry valid.

---

# 25. USER WORKFLOW

User journey harus menjadi:

```text
OPEN APP
   ↓
CHECK MARKET STATUS
   ↓
SEE TOP ACTIONABLE SIGNALS
   ↓
CLICK STOCK
   ↓
UNDERSTAND WHY
   ↓
CHECK ENTRY VALIDITY
   ↓
CHECK TRADE PLAN
   ↓
CHECK AI / NEWS
   ↓
DECIDE
   ↓
ADD TO PORTFOLIO / WATCH
```

---

# 26. EMPTY STATE

Setiap halaman harus memiliki empty state yang menjelaskan apa yang harus dilakukan.

Contoh Dashboard:

```text
No fresh READY signals.

Last scan:
10 minutes ago

Try:
Run Screener
```

Screener:

```text
No READY candidates.

Possible reasons:
- Market conditions are weak
- Risk/Reward requirements not met
- No valid setup

[Run Screener]
```

Jangan hanya menampilkan:

```text
No data.
```

---

# 27. SIGNAL DETAIL / TOOLTIP

Tambahkan tooltip untuk istilah yang berpotensi membingungkan:

```text
Score
Grade
Setup
Status
RR
Entry Zone
Freshness
Dist EMA9
```

Contoh:

```text
Signal Score
Quality score from the technical signal engine.
It is NOT a probability of profit.
```

---

# 28. JANGAN LAKUKAN

Dalam P0:

* Jangan menambah indikator baru
* Jangan mengubah formula RSI
* Jangan mengubah EMA9/EMA21
* Jangan mengubah formula ATR
* Jangan mengganti strategy PULLBACK
* Jangan mengganti strategy BREAKOUT
* Jangan memasukkan AI ke dalam score
* Jangan menghapus portfolio
* Jangan mengubah backtest strategy
* Jangan membuat score menjadi probability
* Jangan membuat AI overwrite system signal
* Jangan melakukan redesign total yang menghilangkan informasi existing

P0 adalah:

> **clarity + consistency + workflow**

---

# 29. BACKEND ACCEPTANCE CRITERIA

P0 dianggap selesai jika:

### Signal

* [ ] Tidak ada lagi READY >=70
* [ ] READY hanya menggunakan `MIN_SIGNAL_SCORE`
* [ ] Score tetap 0–100
* [ ] Grade konsisten
* [ ] Status konsisten
* [ ] Entry validity tersedia
* [ ] Signal timestamp tersedia
* [ ] Signal freshness tersedia
* [ ] Next action tersedia

### API

API stock/signal harus mengembalikan informasi:

```text
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
entry_validity
freshness
signal_generated_at
signal_age
primary_reason
next_action
```

Jika endpoint existing memiliki struktur berbeda, pertahankan backward compatibility dan tambahkan field baru.

---

# 30. UI ACCEPTANCE CRITERIA

User yang baru membuka aplikasi harus bisa menjawab 5 pertanyaan berikut tanpa membaca dokumentasi:

1. **Market sekarang bagaimana?**
2. **Saham mana yang paling menarik?**
3. **Kenapa saham tersebut menarik?**
4. **Apakah sekarang masih boleh entry?**
5. **Kalau entry, bagaimana trade plan-nya?**

Jika salah satu pertanyaan membutuhkan user membuka dokumentasi atau menebak dari warna/angka, UI belum selesai.

---

# 31. FINAL UX PRINCIPLE

Gunakan prinsip:

```text
DON'T MAKE USER INTERPRET THE SYSTEM.
MAKE THE SYSTEM EXPLAIN ITSELF.
```

Prioritas informasi:

```text
ACTION
  ↓
STATUS
  ↓
WHY
  ↓
TRADE PLAN
  ↓
DETAILS
  ↓
RAW INDICATORS
```

Bukan:

```text
INDICATORS
  ↓
SCORE
  ↓
USER FIGURES OUT WHAT TO DO
```

---

# 32. OUTPUT YANG DIMINTA DARI CODING AGENT

Sebelum coding:

1. Audit code existing.
2. Identifikasi file yang menentukan:

   * score
   * grade
   * status
   * READY
   * entry zone
   * scanner ranking
3. Identifikasi endpoint yang mengirim data tersebut ke frontend.
4. Identifikasi template dan JS yang menampilkan signal.

Setelah audit:

Tampilkan rencana perubahan file.

Kemudian implementasikan P0.

Setelah implementasi:

1. Jalankan test.
2. Pastikan existing API tidak rusak.
3. Pastikan scanner tetap berjalan.
4. Pastikan backtest tetap berjalan.
5. Pastikan AI tetap berjalan.
6. Pastikan portfolio tetap berjalan.
7. Pastikan tidak ada hardcoded READY threshold yang conflicting.
8. Update `APP_DOCUMENTATION.md` agar mencerminkan definisi P0 terbaru.

---

# 33. DEFINITION OF DONE

P0 selesai apabila aplikasi terasa seperti:

```text
MARKET
   ↓
FIND
   ↓
EVALUATE
   ↓
PLAN
   ↓
DECIDE
   ↓
MONITOR
```

dan bukan lagi:

```text
Dashboard
→ banyak angka
→ banyak tabel
→ user bingung harus klik apa
```

Target akhir:

> **Dalam waktu kurang dari 10 detik setelah membuka dashboard, user tahu saham apa yang harus diperhatikan dan mengapa.**

> **Dalam waktu kurang dari 30 detik setelah membuka detail saham, user tahu apakah entry masih valid, di harga berapa, SL di mana, TP di mana, dan apa alasan signal tersebut.**
