"""
Portfolio AI Analyst — Rekomendasi AI untuk Portfolio Management.

Reuse existing Google Gemini API infrastructure dari ai_analyst.py.
Tidak membuat provider AI baru — hanya buat prompt dan parser baru.

Fitur:
    1. Per-posisi AI analysis → 9 action pilihan
    2. Portfolio-level AI analysis → Portfolio Health Score 0–100

Actions tersedia:
    STRONG_HOLD, HOLD, WATCH, TIGHTEN_STOP_LOSS,
    TAKE_PROFIT_PARTIAL, TAKE_PROFIT, CUT_LOSS, EXIT, INSUFFICIENT_DATA

PENTING: AI hanya menganalisis data yang disediakan — tidak mengarang
         data harga, fundamental, atau kondisi pasar yang tidak ada.
"""

import httpx
import json
import logging
from typing import Dict, Any, Optional, List

from app import config

logger = logging.getLogger("app.portfolio_ai")

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"

VALID_ACTIONS = {
    "STRONG_HOLD", "HOLD", "WATCH", "TIGHTEN_STOP_LOSS",
    "TAKE_PROFIT_PARTIAL", "TAKE_PROFIT", "CUT_LOSS", "EXIT", "INSUFFICIENT_DATA"
}

VALID_CONFIDENCE = {"HIGH", "MEDIUM", "LOW"}

PORTFOLIO_SYSTEM_PROMPT = """Kamu adalah Portfolio Manager profesional untuk saham Indonesia (IDX/BEI).
Tugasmu adalah menganalisis portofolio saham berdasarkan data yang TERSEDIA dalam input.

ATURAN KETAT:
1. Kamu HANYA boleh menganalisis berdasarkan data yang secara eksplisit diberikan.
2. Kamu TIDAK BOLEH mengklaim memiliki akses ke: data realtime, order book, berita, fundamental perusahaan, atau data eksternal lain yang tidak ada dalam input.
3. Jika data tidak cukup, gunakan action "INSUFFICIENT_DATA".
4. Semua output HARUS dalam format JSON valid sesuai skema yang diminta.
5. Jawab dalam Bahasa Indonesia yang jelas dan profesional.
6. Jangan menyarankan aksi beli/jual otomatis — hanya rekomendasi analisis."""


# ─── Per-Position Prompt ───────────────────────────────────

def _build_position_prompt(enriched: dict) -> str:
    """Bangun prompt analisis untuk satu posisi saham."""
    sym      = enriched.get("symbol_short", enriched.get("symbol", ""))
    name     = enriched.get("display_name", "")
    lots     = enriched.get("quantity_lots", 0)
    shares   = enriched.get("shares", lots * 100)
    avg_buy  = enriched.get("avg_buy_price", 0)
    cur_price= enriched.get("current_price")
    invested = enriched.get("invested")
    cur_val  = enriched.get("current_value")
    pnl      = enriched.get("unrealized_pnl")
    pnl_pct  = enriched.get("pnl_pct")
    days     = enriched.get("holding_days", 0)
    price_status = enriched.get("price_status", "unavailable")
    target   = enriched.get("target_price")
    sl       = enriched.get("stop_loss_price")
    notes    = enriched.get("notes") or "Tidak ada catatan"

    # Technical
    tech_ok  = enriched.get("technical_available", False)
    rsi      = enriched.get("rsi")
    ema9     = enriched.get("ema9")
    ema21    = enriched.get("ema21")
    vol_rat  = enriched.get("volume_ratio")
    sw_score = enriched.get("swing_score")
    sw_grade = enriched.get("swing_grade")
    sw_stat  = enriched.get("swing_status")
    dist_sl  = enriched.get("dist_to_sl_pct")
    dist_tp  = enriched.get("dist_to_target_pct")

    price_note = "DELAYED ~15-20 menit dari Yahoo Finance" if price_status == "delayed" else "TIDAK TERSEDIA"

    cur_price_str = f"Rp {cur_price:,.0f}" if cur_price is not None else "TIDAK TERSEDIA"
    invested_str  = f"Rp {invested:,.0f}" if invested is not None else "N/A"
    cur_val_str   = f"Rp {cur_val:,.0f}" if cur_val is not None else "N/A"
    pnl_str       = f"Rp {pnl:+,.0f}" if pnl is not None else "N/A"
    pnl_pct_str   = f"{pnl_pct:+.2f}%" if pnl_pct is not None else "N/A"
    target_str    = f"Rp {target:,.0f}" if target is not None else "Tidak diset"
    sl_str        = f"Rp {sl:,.0f}" if sl is not None else "Tidak diset"

    prompt = f"""Analisis posisi saham berikut dalam portofolio saya:

=== INFORMASI POSISI ===
Saham   : {sym} — {name}
Posisi  : {lots} lot ({shares:,} saham)
Harga Beli Rata-rata : Rp {avg_buy:,.0f}
Harga Sekarang      : {cur_price_str} ({price_note})
Nilai Investasi     : {invested_str}
Nilai Sekarang      : {cur_val_str}
Unrealized P/L      : {pnl_str} ({pnl_pct_str})
Durasi Holding      : {days} hari
Target Harga        : {target_str}
Stop Loss           : {sl_str}
Catatan User        : {notes}
"""

    if dist_tp is not None:
        prompt += f"Jarak ke Target     : {dist_tp:+.2f}%\n"
    if dist_sl is not None:
        prompt += f"Jarak ke Stop Loss  : {dist_sl:+.2f}%\n"

    if tech_ok:
        rsi_str    = f"{rsi:.1f}" if rsi is not None else "N/A"
        ema9_str   = f"Rp {ema9:,.0f}" if ema9 is not None else "N/A"
        ema21_str  = f"Rp {ema21:,.0f}" if ema21 is not None else "N/A"
        vol_str    = f"{vol_rat:.2f}x" if vol_rat is not None else "N/A"
        sw_sc_str  = f"{sw_score}/100" if sw_score is not None else "N/A"
        prompt += f"""
=== DATA TEKNIKAL (dari sistem rule-based) ===
RSI (14)       : {rsi_str}
EMA 9          : {ema9_str}
EMA 21         : {ema21_str}
Volume Ratio   : {vol_str}
Swing Score    : {sw_sc_str}
Swing Grade    : {sw_grade or 'N/A'}
Swing Status   : {sw_stat or 'N/A'}
"""
    else:
        prompt += "\n=== DATA TEKNIKAL ===\nTidak tersedia (saham belum ada dalam universe screener)\n"


    prompt += """
=== FORMAT OUTPUT ===

Kembalikan HANYA JSON valid berikut tanpa penjelasan tambahan:
{
  "action": "<STRONG_HOLD|HOLD|WATCH|TIGHTEN_STOP_LOSS|TAKE_PROFIT_PARTIAL|TAKE_PROFIT|CUT_LOSS|EXIT|INSUFFICIENT_DATA>",
  "confidence": "<HIGH|MEDIUM|LOW>",
  "summary": "Ringkasan kondisi posisi dalam 1-2 kalimat.",
  "reason": ["alasan 1", "alasan 2", "alasan 3"],
  "risk": ["risiko 1", "risiko 2"],
  "suggested_action": "Saran konkret dalam 1 kalimat.",
  "suggested_take_profit": <number atau null>,
  "suggested_stop_loss": <number atau null>,
  "suggested_sell_percentage": <number 0-100 atau null, khusus untuk TAKE_PROFIT_PARTIAL>
}"""

    return prompt


# ─── Portfolio-Level Prompt ────────────────────────────────

def _build_portfolio_prompt(enriched_holdings: List[dict], summary: dict) -> str:
    """Bangun prompt analisis untuk keseluruhan portofolio."""
    total_invested = summary.get("total_invested", 0)
    total_value    = summary.get("total_current_value", 0)
    total_pnl      = summary.get("total_unrealized_pnl", 0)
    total_pct      = summary.get("total_pnl_pct", 0)
    n_holdings     = summary.get("num_holdings", 0)
    n_profit       = summary.get("num_profitable", 0)
    n_loss         = summary.get("num_losing", 0)

    prompt = f"""Analisis portofolio saham IDX saya secara keseluruhan:

=== RINGKASAN PORTOFOLIO ===
Total Investasi    : Rp {total_invested:,.0f}
Total Nilai Kini   : Rp {total_value:,.0f}
Unrealized P/L     : Rp {total_pnl:+,.0f} ({total_pct:+.2f}%)
Jumlah Holdings    : {n_holdings} saham
Posisi Untung      : {n_profit}
Posisi Rugi        : {n_loss}
Data Harga         : DELAYED ~15-20 menit (Yahoo Finance)

=== DETAIL POSISI ===
"""

    for e in enriched_holdings:
        sym      = e.get("symbol_short", e.get("symbol", ""))
        lots     = e.get("quantity_lots", 0)
        pnl_pct  = e.get("pnl_pct")
        pnl      = e.get("unrealized_pnl")
        sw_score = e.get("swing_score")
        sw_stat  = e.get("swing_status")
        invested_pct = 0
        if total_invested > 0 and e.get("invested"):
            invested_pct = e["invested"] / total_invested * 100

        prompt += f"- {sym}: {lots} lot | "
        if pnl_pct is not None:
            prompt += f"P/L: {pnl_pct:+.2f}% (Rp {pnl:+,.0f}) | "
        else:
            prompt += "P/L: Data tidak tersedia | "
        prompt += f"Alokasi: {invested_pct:.1f}%"
        if sw_score is not None:
            prompt += f" | Swing Score: {sw_score}/100 ({sw_stat})"
        prompt += "\n"

    prompt += """
=== FORMAT OUTPUT ===
Kembalikan HANYA JSON valid berikut:
{
  "portfolio_score": <integer 0-100>,
  "health_status": "<EXCELLENT|GOOD|FAIR|RISKY|HIGH_RISK>",
  "summary": "Ringkasan kondisi portofolio dalam 2-3 kalimat.",
  "concentration_risk": "Evaluasi risiko konsentrasi portofolio.",
  "positions_requiring_attention": ["symbol1", "symbol2"],
  "actions": [
    {"symbol": "...", "action": "...", "confidence": "...", "brief": "..."}
  ],
  "biggest_winner": "<symbol atau null>",
  "biggest_loser": "<symbol atau null>",
  "key_risks": ["risiko 1", "risiko 2"],
  "suggestions": ["saran 1", "saran 2"]
}

Kriteria health_status:
90-100 = EXCELLENT, 80-89 = GOOD, 70-79 = FAIR, 60-69 = RISKY, <60 = HIGH_RISK"""

    return prompt


# ─── Gemini API Call ───────────────────────────────────────

async def _call_gemini(prompt: str) -> Optional[str]:
    """
    Panggil Google Gemini API (reuse config dari ai_analyst.py).
    Return raw text response, atau None jika error.
    """
    if not config.AI_ENABLED:
        return None

    api_key = config.GEMINI_API_KEY.strip()
    if not api_key:
        return None

    model = config.GEMINI_MODEL.strip() or "gemini-2.0-flash"
    url   = f"{GEMINI_API_URL}/{model}:generateContent?key={api_key}"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": PORTFOLIO_SYSTEM_PROMPT}]},
        "generationConfig": {
            "temperature": 0.15,
            "responseMimeType": "application/json"
        }
    }

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code != 200:
                logger.error(f"Gemini Portfolio API error ({response.status_code}): {response.text[:200]}")
                return None

            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return None

            return candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")

    except httpx.TimeoutException:
        logger.warning("Portfolio AI Gemini API timed out (>45s).")
        return None
    except Exception as e:
        logger.error(f"Portfolio AI unexpected error: {e}", exc_info=True)
        return None


def _parse_json_response(raw: str) -> Optional[dict]:
    """Parse dan bersihkan JSON response dari Gemini."""
    if not raw:
        return None
    raw = raw.strip()
    # Bersihkan markdown code block
    if raw.startswith("```json"):
        raw = raw[7:]
    elif raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    # Ambil JSON object pertama
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start != -1 and end > start:
        raw = raw[start:end]

    try:
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"Portfolio AI JSON parse error: {e}. Raw: {raw[:200]}")
        return None


# ─── Public API ────────────────────────────────────────────

async def analyze_position(enriched: dict) -> dict:
    """
    Analisis AI untuk satu posisi saham.

    Args:
        enriched: dict dari portfolio_service.enrich_holding()

    Returns:
        dict: action, confidence, summary, reason, risk,
              suggested_action, suggested_take_profit, suggested_stop_loss,
              suggested_sell_percentage, model_used, ai_available
    """
    if not config.AI_ENABLED or not config.GEMINI_API_KEY.strip():
        return {
            "ai_available":  False,
            "action":        "INSUFFICIENT_DATA",
            "confidence":    "LOW",
            "summary":       "AI analysis tidak tersedia. Pastikan GEMINI_API_KEY diisi di .env",
            "reason":        [],
            "risk":          [],
            "suggested_action": "AI tidak dikonfigurasi.",
        }

    sym   = enriched.get("symbol_short", enriched.get("symbol", ""))
    prompt = _build_position_prompt(enriched)
    raw   = await _call_gemini(prompt)

    if raw is None:
        return {
            "ai_available": False,
            "action":       "INSUFFICIENT_DATA",
            "confidence":   "LOW",
            "summary":      "AI analysis unavailable — coba lagi.",
            "reason":       [],
            "risk":         [],
        }

    data = _parse_json_response(raw)
    if not data:
        return {
            "ai_available": True,
            "action":       "INSUFFICIENT_DATA",
            "confidence":   "LOW",
            "summary":      "Format respons AI tidak valid.",
            "reason":       [],
            "risk":         [],
        }

    # Normalisasi dan validasi fields
    action = str(data.get("action", "INSUFFICIENT_DATA")).upper()
    if action not in VALID_ACTIONS:
        action = "INSUFFICIENT_DATA"

    confidence = str(data.get("confidence", "LOW")).upper()
    if confidence not in VALID_CONFIDENCE:
        confidence = "MEDIUM"

    model = config.GEMINI_MODEL.strip() or "gemini-2.0-flash"
    logger.info(f"Portfolio AI [{sym}]: action={action}, confidence={confidence}")

    return {
        "ai_available":             True,
        "action":                   action,
        "confidence":               confidence,
        "summary":                  str(data.get("summary", "")),
        "reason":                   list(data.get("reason", [])),
        "risk":                     list(data.get("risk", [])),
        "suggested_action":         str(data.get("suggested_action", "")),
        "suggested_take_profit":    data.get("suggested_take_profit"),
        "suggested_stop_loss":      data.get("suggested_stop_loss"),
        "suggested_sell_percentage":data.get("suggested_sell_percentage"),
        "model_used":               f"Google {model}",
        "symbol":                   sym,
    }


async def analyze_portfolio(enriched_holdings: List[dict], summary: dict) -> dict:
    """
    Analisis AI untuk keseluruhan portofolio.

    Returns:
        dict: portfolio_score, health_status, summary, concentration_risk,
              positions_requiring_attention, actions, biggest_winner, biggest_loser,
              key_risks, suggestions, model_used
    """
    if not config.AI_ENABLED or not config.GEMINI_API_KEY.strip():
        return {
            "ai_available":  False,
            "portfolio_score": 0,
            "health_status": "INSUFFICIENT_DATA",
            "summary":       "AI analysis tidak tersedia. Pastikan GEMINI_API_KEY diisi di .env",
        }

    if not enriched_holdings:
        return {
            "ai_available":  True,
            "portfolio_score": 0,
            "health_status": "INSUFFICIENT_DATA",
            "summary":       "Portfolio kosong — tidak ada posisi untuk dianalisis.",
        }

    prompt = _build_portfolio_prompt(enriched_holdings, summary)
    raw    = await _call_gemini(prompt)

    if raw is None:
        return {
            "ai_available":  False,
            "portfolio_score": 0,
            "health_status": "INSUFFICIENT_DATA",
            "summary":       "AI Portfolio analysis unavailable — coba lagi.",
        }

    data = _parse_json_response(raw)
    if not data:
        return {
            "ai_available":  True,
            "portfolio_score": 0,
            "health_status": "INSUFFICIENT_DATA",
            "summary":       "Format respons AI Portfolio tidak valid.",
        }

    # Normalisasi portfolio_score
    score = int(data.get("portfolio_score", 50))
    score = max(0, min(100, score))

    valid_health = {"EXCELLENT", "GOOD", "FAIR", "RISKY", "HIGH_RISK"}
    health = str(data.get("health_status", "FAIR")).upper()
    if health not in valid_health:
        health = "FAIR"

    model = config.GEMINI_MODEL.strip() or "gemini-2.0-flash"
    logger.info(f"Portfolio AI: score={score}, health={health}")

    return {
        "ai_available":                  True,
        "portfolio_score":               score,
        "health_status":                 health,
        "summary":                       str(data.get("summary", "")),
        "concentration_risk":            str(data.get("concentration_risk", "")),
        "positions_requiring_attention": list(data.get("positions_requiring_attention", [])),
        "actions":                       list(data.get("actions", [])),
        "biggest_winner":                data.get("biggest_winner"),
        "biggest_loser":                 data.get("biggest_loser"),
        "key_risks":                     list(data.get("key_risks", [])),
        "suggestions":                   list(data.get("suggestions", [])),
        "model_used":                    f"Google {model}",
    }
