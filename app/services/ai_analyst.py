"""
AI Analyst Service — Powered by Google Gemini API (Free Tier)
Menganalisis data teknikal + berita terkini saham IDX, menghasilkan:
- Rekomendasi: BUY / HOLD / SELL (dikaitkan dengan berita nyata)
- AI Confidence Score (0-100)
- Risiko & peluang spesifik
- Konteks berita konkret (bukan boilerplate)
- Kompatibel untuk deployment di Vercel/Cloud (serverless ready)
"""
import httpx
import json
import logging
import urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from app import config

logger = logging.getLogger("app.ai")

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"

SYSTEM_PROMPT = """Kamu adalah analis trading saham Indonesia (IDX) profesional dan objektif.
Tugasmu adalah menganalisis data teknikal + berita terkini saham dan memberikan rekomendasi dalam Bahasa Indonesia yang tajam, spesifik, dan dapat dipahami trader.

ATURAN WAJIB:
1. Jika ada berita: sebutkan judul/sumbernya secara eksplisit dalam analisis dan news_context.
2. Jika tidak ada berita: nyatakan itu secara tegas, JANGAN generalisasi sektor.
3. DILARANG menggunakan kalimat klise tanpa data: "sensitif terhadap fluktuasi global", "kondisi pasar yang dinamis", dll.
4. news_context HARUS merujuk berita nyata yang diberikan, bukan asumsi.
5. Format output HARUS selalu berupa valid JSON sesuai skema yang diminta."""

ANALYSIS_PROMPT_TEMPLATE = """Analisis saham {TICKER} ({SECTOR}) untuk keputusan trading hari ini.

DATA TEKNIKAL:
- Harga: Rp{PRICE:,.0f} | EMA9: Rp{EMA9:,.0f} | EMA21: Rp{EMA21:,.0f} | RSI: {RSI:.1f}
- Volume: {VOLUME:,.0f} ({VOLUME_CHANGE:+.1f}% vs rata-rata)
- Support: {SUPPORT} | Resistance: {RESISTANCE}
- Entry zone: Rp{ENTRY_LOW:,.0f} – Rp{ENTRY_HIGH:,.0f} | SL: Rp{SL:,.0f} | TP1: Rp{TP1:,.0f} | TP2: Rp{TP2:,.0f}

SIGNAL SISTEM:
- Setup: {SETUP} | Grade: {GRADE} | Score: {SCORE}/100 | Status: {STATUS}
- Risk/Reward: 1:{RR:.2f}

BERITA TERKINI (3 hari terakhir):
{NEWS_HEADLINES}

INSTRUKSI:
- Wajib kaitkan rekomendasi dengan berita di atas jika ada, sebutkan judul/isinya secara spesifik.
- Jika tidak ada berita relevan, katakan itu secara eksplisit, jangan generalisasi sektor.
- Dilarang pakai kalimat generik seperti "sensitif terhadap fluktuasi global" tanpa data pendukung konkret.
- Berikan: rekomendasi (BUY/HOLD/SELL), confidence (0-100), risiko (max 3 poin spesifik), peluang (max 3 poin spesifik), konteks berita (1-2 kalimat merujuk berita nyata).

Format JSON:
{{
  "recommendation": "<BUY|HOLD|SELL>",
  "confidence": <integer 0-100>,
  "risks": ["risiko 1 (spesifik)", "risiko 2", "risiko 3"],
  "opportunities": ["peluang 1 (spesifik)", "peluang 2", "peluang 3"],
  "news_context": "1-2 kalimat menyebut berita nyata secara konkret."
}}"""


# ── News Fetcher ─────────────────────────────────────────────────────────────

async def fetch_stock_news(ticker: str, max_items: int = 5) -> str:
    """
    Mengambil berita saham 3 hari terakhir via Google News RSS.
    Returns formatted string untuk dimasukkan ke prompt AI.
    """
    clean = ticker.replace(".JK", "").strip()
    query = f"{clean} saham"
    url = (
        f"https://news.google.com/rss/search"
        f"?q={urllib.parse.quote(query)}&hl=id&gl=ID&ceid=ID:id"
    )
    headers = {"User-Agent": "Mozilla/5.0 (compatible; AsykarDayTrade/1.0)"}
    now = datetime.now(timezone.utc)

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(url, headers=headers, follow_redirects=True)
            r.raise_for_status()

        root = ET.fromstring(r.text)
        items = root.findall(".//item")

        headlines: List[str] = []
        for it in items:
            title = it.findtext("title", "").strip()
            source = it.findtext("source", "").strip()
            pub_str = it.findtext("pubDate", "")

            try:
                dt = parsedate_to_datetime(pub_str)
                age_days = (now - dt).total_seconds() / 86400.0
            except Exception:
                age_days = 0.0

            if age_days <= 3.5 and title:
                label = f"- {title}"
                if source:
                    label += f" ({source})"
                headlines.append(label)

            if len(headlines) >= max_items:
                break

        if not headlines:
            return "Tidak ada berita signifikan"

        return "\n".join(headlines)

    except Exception as e:
        logger.warning(f"fetch_stock_news({ticker}) failed: {e}")
        return "Tidak ada berita signifikan"


# ── Prompt Builder ────────────────────────────────────────────────────────────

async def _build_prompt(signal: Dict[str, Any]) -> str:
    """Membangun prompt analisis dari data signal + berita terkini."""
    ticker = signal.get("symbol", "???")
    sector = signal.get("sector", "Umum")
    price = signal.get("current_price") or signal.get("price", 0)
    ema9 = signal.get("ema9", price)
    ema21 = signal.get("ema21", price)
    rsi = signal.get("rsi", 50.0)
    volume = signal.get("volume", 0)
    vol_ratio = signal.get("volume_ratio", 1.0)
    volume_change = (vol_ratio - 1.0) * 100.0
    support = signal.get("support_zone", "-")
    resistance = signal.get("resistance_zone", "-")
    entry_low = signal.get("entry_low", price)
    entry_high = signal.get("entry_high", price)
    sl = signal.get("stop_loss", price * 0.96)
    tp1 = signal.get("tp1", price * 1.04)
    tp2 = signal.get("tp2", price * 1.08)
    setup = signal.get("setup", "NONE")
    grade = signal.get("grade", "-")
    score = signal.get("score", 0)
    status = signal.get("status", "-")
    rr = signal.get("risk_reward", 0.0)

    # Fetch news (async, with 5s timeout built-in)
    news_headlines = await fetch_stock_news(ticker)

    return ANALYSIS_PROMPT_TEMPLATE.format(
        TICKER=ticker.replace(".JK", ""),
        SECTOR=sector,
        PRICE=price,
        EMA9=ema9,
        EMA21=ema21,
        RSI=rsi,
        VOLUME=volume,
        VOLUME_CHANGE=volume_change,
        SUPPORT=support,
        RESISTANCE=resistance,
        ENTRY_LOW=entry_low,
        ENTRY_HIGH=entry_high,
        SL=sl,
        TP1=tp1,
        TP2=tp2,
        SETUP=setup,
        GRADE=grade,
        SCORE=score,
        STATUS=status,
        RR=rr,
        NEWS_HEADLINES=news_headlines,
    )


# ── Response Parser ───────────────────────────────────────────────────────────

def _parse_ai_response(raw: str) -> Dict[str, Any]:
    """Parse JSON response dari Gemini model (schema baru + alias legacy)."""
    raw = raw.strip()

    # Bersihkan markdown codeblock jika ada
    if raw.startswith("```json"):
        raw = raw[7:]
    elif raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    # Extract JSON object
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start != -1 and end > start:
        raw = raw[start:end]

    try:
        data = json.loads(raw)

        # ── New schema (BUY/HOLD/SELL) ─────────────────────────────────────
        rec = str(data.get("recommendation", data.get("ai_recommendation", "HOLD"))).upper()
        if rec not in ("BUY", "HOLD", "SELL", "WAIT", "AVOID"):
            rec = "HOLD"
        # Normalise legacy values
        if rec == "WAIT":
            rec = "HOLD"
        if rec == "AVOID":
            rec = "SELL"

        confidence = int(data.get("confidence", data.get("ai_confidence", 50)))
        confidence = max(0, min(100, confidence))

        risks = list(data.get("risks", data.get("ai_risks", [])))
        opportunities = list(data.get("opportunities", data.get("ai_opportunities", [])))
        news_context = str(
            data.get("news_context", data.get("ai_market_context", "Tidak ada konteks berita tersedia."))
        )
        summary = str(data.get("ai_summary", news_context))

        return {
            # New schema
            "recommendation": rec,
            "confidence": confidence,
            "risks": risks,
            "opportunities": opportunities,
            "news_context": news_context,
            # Legacy aliases (backward compat with existing templates)
            "ai_recommendation": rec,
            "ai_confidence": confidence,
            "ai_risks": risks,
            "ai_opportunities": opportunities,
            "ai_market_context": news_context,
            "ai_summary": summary,
            "ai_recommendation_reason": "",
            "parse_ok": True,
        }

    except Exception as e:
        logger.warning(f"AI response JSON parse failed: {e}. Raw: {raw[:200]}")
        return {
            "recommendation": "HOLD",
            "confidence": 50,
            "risks": [],
            "opportunities": [],
            "news_context": "Format respons tidak dapat diparsing.",
            # Legacy
            "ai_recommendation": "HOLD",
            "ai_confidence": 50,
            "ai_risks": [],
            "ai_opportunities": [],
            "ai_market_context": "",
            "ai_summary": raw[:300] if raw else "Parse error",
            "ai_recommendation_reason": "",
            "parse_ok": False,
        }


# ── Main Entry Point ──────────────────────────────────────────────────────────

async def analyze_stock(signal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Analisis saham menggunakan Google Gemini API (Free Tier).

    Args:
        signal: Dict hasil dari scanner_service.process_symbol_detail()

    Returns:
        Dict berisi hasil analisis AI, atau Dict error jika API Key belum dipasang.
    """
    if not config.AI_ENABLED:
        logger.info("AI analysis disabled via AI_ENABLED=false")
        return None

    api_key = config.GEMINI_API_KEY.strip()
    if not api_key:
        logger.warning("GEMINI_API_KEY is not set in environment.")
        return {
            "error": "missing_api_key",
            "message": "GEMINI_API_KEY belum diisi di file .env. Dapatkan API Key gratis di https://aistudio.google.com/app/apikey",
            "ai_enabled": True
        }

    # Build prompt (async — includes news fetch)
    prompt = await _build_prompt(signal)
    model = config.GEMINI_MODEL.strip() or "gemini-2.0-flash"

    url = f"{GEMINI_API_URL}/{model}:generateContent?key={api_key}"

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "systemInstruction": {
            "parts": [
                {"text": SYSTEM_PROMPT}
            ]
        },
        "generationConfig": {
            "temperature": 0.25,
            "responseMimeType": "application/json"
        }
    }

    try:
        async with httpx.AsyncClient(timeout=35.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code != 200:
                err_body = response.text
                logger.error(f"Gemini API error ({response.status_code}): {err_body}")
                return {
                    "error": "api_error",
                    "status_code": response.status_code,
                    "message": f"Gemini API error ({response.status_code}): Pastikan GEMINI_API_KEY valid di .env",
                    "details": err_body[:200]
                }

            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return {
                    "error": "no_candidates",
                    "message": "Gemini tidak mengembalikan output untuk saham ini."
                }

            raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            result = _parse_ai_response(raw_text)
            result["model_used"] = f"Google {model}"
            result["symbol"] = signal.get("symbol", "")

            logger.info(
                f"Gemini AI analysis done for {signal.get('symbol')} — "
                f"rec={result['recommendation']} confidence={result['confidence']}"
            )
            return result

    except httpx.TimeoutException:
        logger.warning("Gemini API request timed out (>35s).")
        return {
            "error": "timeout",
            "message": "Permintaan ke Google Gemini API timed out. Silakan coba lagi."
        }
    except Exception as e:
        logger.error(f"Gemini AI analysis unexpected error: {e}", exc_info=True)
        return {
            "error": "internal_error",
            "message": f"Terjadi kesalahan saat memproses analisis AI: {str(e)}"
        }


async def check_gemini_status() -> Dict[str, Any]:
    """Cek konfigurasi dan koneksi ke Google Gemini API."""
    api_key = config.GEMINI_API_KEY.strip()
    has_key = bool(api_key)
    model = config.GEMINI_MODEL.strip() or "gemini-2.0-flash"

    return {
        "provider": "Google Gemini API",
        "configured_model": model,
        "api_key_configured": has_key,
        "ai_enabled": config.AI_ENABLED,
        "free_tier_info": "Google AI Studio Free Tier (Gemini 2.5 Flash / 2.0 Flash)",
        "news_source": "Google News RSS (ID)"
    }
