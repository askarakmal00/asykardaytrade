"""
Portfolio Service — Kalkulasi P/L, enrichment market data, dan summary.

Tanggung jawab:
    - Hitung P/L per posisi (formula lot × 100 × harga)
    - Ambil harga terkini dari existing Yahoo Finance provider
    - Enrichment dengan data teknikal dari existing scanner_service
    - Hitung portfolio summary (total invested, current value, return)
    - Siapkan data input untuk AI Portfolio Analyst

Tidak membuat sistem market data baru — reuse existing provider.
"""

import datetime
import math
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.database import repositories
from app.database.models import PortfolioHolding
from app.providers.tradingview import TradingViewProvider

logger = logging.getLogger("app.portfolio")

_provider = TradingViewProvider()


# ─── Helpers ───────────────────────────────────────────────

def _safe(v, default=None):
    try:
        f = float(v)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def _holding_to_dict(h: PortfolioHolding) -> dict:
    """Ubah ORM object ke plain dict."""
    return {
        "id":              h.id,
        "symbol":          h.symbol,
        "company_name":    h.company_name or "",
        "quantity_lots":   h.quantity_lots,
        "avg_buy_price":   h.avg_buy_price,
        "buy_date":        h.buy_date,
        "target_price":    h.target_price,
        "stop_loss_price": h.stop_loss_price,
        "notes":           h.notes or "",
        "created_at":      h.created_at.isoformat() if h.created_at else None,
        "updated_at":      h.updated_at.isoformat() if h.updated_at else None,
    }


# ─── P/L Calculation ───────────────────────────────────────

def calculate_position_metrics(holding_dict: dict, current_price: Optional[float]) -> dict:
    """
    Hitung semua metric finansial untuk satu posisi.

    Konvensi IDX:
        1 lot = 100 saham
        invested       = lots × 100 × avg_buy_price
        current_value  = lots × 100 × current_price
        unrealized_pnl = current_value - invested
        pnl_pct        = unrealized_pnl / invested × 100

    Args:
        holding_dict: dict dari _holding_to_dict()
        current_price: harga terkini (bisa None jika tidak tersedia)

    Returns:
        dict metrics: shares, invested, current_value, unrealized_pnl, pnl_pct,
                      holding_days, dist_to_target_pct, dist_to_sl_pct, price_status
    """
    lots           = int(holding_dict.get("quantity_lots", 0))
    avg_buy        = _safe(holding_dict.get("avg_buy_price", 0))
    buy_date_str   = holding_dict.get("buy_date", "")
    target_price   = _safe(holding_dict.get("target_price"))
    stop_loss      = _safe(holding_dict.get("stop_loss_price"))

    shares   = lots * 100
    invested = shares * (avg_buy or 0)

    # Holding duration
    holding_days = 0
    try:
        buy_dt    = datetime.datetime.strptime(buy_date_str, "%Y-%m-%d")
        holding_days = (datetime.datetime.now() - buy_dt).days
    except Exception:
        pass

    # P/L — hanya bisa dihitung jika ada harga
    if current_price is not None and current_price > 0 and invested > 0:
        current_value  = shares * current_price
        unrealized_pnl = current_value - invested
        pnl_pct        = (unrealized_pnl / invested) * 100
        price_status   = "delayed"
    else:
        current_value  = None
        unrealized_pnl = None
        pnl_pct        = None
        price_status   = "unavailable"

    # Jarak ke target dan SL
    dist_to_target_pct = None
    dist_to_sl_pct     = None
    if current_price and target_price and current_price > 0:
        dist_to_target_pct = round((target_price - current_price) / current_price * 100, 2)
    if current_price and stop_loss and current_price > 0:
        dist_to_sl_pct = round((current_price - stop_loss) / current_price * 100, 2)

    return {
        "shares":             shares,
        "invested":           round(invested, 0) if invested else None,
        "current_price":      round(current_price, 2) if current_price else None,
        "current_value":      round(current_value, 0) if current_value else None,
        "unrealized_pnl":     round(unrealized_pnl, 0) if unrealized_pnl is not None else None,
        "pnl_pct":            round(pnl_pct, 2) if pnl_pct is not None else None,
        "holding_days":       holding_days,
        "dist_to_target_pct": dist_to_target_pct,
        "dist_to_sl_pct":     dist_to_sl_pct,
        "price_status":       price_status,
    }


# ─── Market Data Fetch ─────────────────────────────────────

def fetch_current_price(symbol: str) -> dict:
    """
    Ambil harga terkini dari Yahoo Finance (existing provider).

    Returns:
        dict: current_price, price_source, price_note, price_status
    """
    try:
        quote = _provider.get_quote(symbol)
        price = _safe(quote.get("current_price"))
        return {
            "current_price": price,
            "price_source":  quote.get("data_source", "Yahoo Finance"),
            "price_note":    quote.get("data_note", "Delayed ~15-20 menit"),
            "price_status":  "delayed" if price else "unavailable",
        }
    except Exception as e:
        logger.warning(f"fetch_current_price error for {symbol}: {e}")
        return {
            "current_price": None,
            "price_source":  "Yahoo Finance",
            "price_note":    "Market data unavailable",
            "price_status":  "unavailable",
        }


# ─── Technical Data Enrichment ─────────────────────────────

def get_technical_data(db: Session, symbol: str) -> dict:
    """
    Ambil data teknikal dari existing scanner untuk satu saham.

    Reuse scanner_service.process_symbol_detail() — tidak duplikasi logika.

    Returns:
        dict: rsi, ema9, ema21, volume_ratio, dist_ema9_pct, swing_score,
              swing_grade, swing_status, swing_setup, atr, support, resistance
    """
    try:
        from app.services.scanner_service import process_symbol_detail
        detail = process_symbol_detail(db, symbol)
        if not detail or detail.get("status") == "DATA_UNAVAILABLE":
            return {"technical_available": False}

        return {
            "technical_available": True,
            "rsi":             _safe(detail.get("rsi")),
            "ema9":            _safe(detail.get("ema9")),
            "ema21":           _safe(detail.get("ema21")),
            "ema50":           _safe(detail.get("ema50")),
            "volume_ratio":    _safe(detail.get("volume_ratio")),
            "dist_ema9_pct":   _safe(detail.get("dist_ema9_pct")),
            "est_value":       _safe(detail.get("est_value")),
            "swing_score":     int(detail.get("score", 0)),
            "swing_grade":     detail.get("grade", ""),
            "swing_status":    detail.get("status", ""),
            "swing_setup":     detail.get("setup", ""),
            "swing_risk_reward": _safe(detail.get("risk_reward")),
            "swing_entry_low": _safe(detail.get("entry_low")),
            "swing_entry_high":_safe(detail.get("entry_high")),
            "swing_sl":        _safe(detail.get("stop_loss")),
            "swing_tp1":       _safe(detail.get("tp1")),
            "swing_tp2":       _safe(detail.get("tp2")),
            "why_this_stock":  detail.get("why_this_stock", []),
            "why_not_ready":   detail.get("why_not_ready", []),
            "sector":          detail.get("sector", ""),
            "name":            detail.get("name", ""),
            "latest_date":     detail.get("latest_date", ""),
        }
    except Exception as e:
        logger.warning(f"get_technical_data error for {symbol}: {e}")
        return {"technical_available": False}


def enrich_holding(db: Session, holding: PortfolioHolding) -> dict:
    """
    Enrichment lengkap untuk satu posisi:
    holding data + market price + P/L metrics + technical data.

    Returns combined dict siap untuk UI dan AI input.
    """
    h = _holding_to_dict(holding)
    symbol = h["symbol"]

    # 1. Harga terkini
    price_data = fetch_current_price(symbol)
    current_price = price_data.get("current_price")

    # 2. P/L metrics
    metrics = calculate_position_metrics(h, current_price)

    # 3. Technical data
    tech = get_technical_data(db, symbol)

    return {
        **h,
        **price_data,
        **metrics,
        **tech,
        "display_name": h.get("company_name") or tech.get("name") or symbol.replace(".JK", ""),
        "symbol_short":  symbol.replace(".JK", ""),
    }



# ─── Portfolio Summary ─────────────────────────────────────

def get_portfolio_summary(db: Session) -> dict:
    """
    Hitung ringkasan keseluruhan portofolio.

    Returns:
        dict:
            total_invested, total_current_value, total_unrealized_pnl,
            total_pnl_pct, num_holdings, num_profitable, num_losing,
            biggest_winner, biggest_loser, enriched_holdings (list)
    """
    holdings = repositories.get_all_holdings(db)
    if not holdings:
        return {
            "total_invested":      0,
            "total_current_value": 0,
            "total_unrealized_pnl": 0,
            "total_pnl_pct":       0,
            "num_holdings":        0,
            "num_profitable":      0,
            "num_losing":          0,
            "num_no_data":         0,
            "biggest_winner":      None,
            "biggest_loser":       None,
            "enriched_holdings":   [],
            "price_note":          "Yahoo Finance — Delayed (~15-20 min)",
        }

    enriched = []
    for h in holdings:
        enriched.append(enrich_holding(db, h))

    # Aggregate
    total_invested      = sum(e.get("invested") or 0 for e in enriched)
    total_current_value = sum(e.get("current_value") or 0 for e in enriched)
    total_unrealized_pnl = total_current_value - total_invested if total_invested else 0
    total_pnl_pct = (total_unrealized_pnl / total_invested * 100) if total_invested > 0 else 0

    profitable = [e for e in enriched if (e.get("unrealized_pnl") or 0) > 0]
    losing     = [e for e in enriched if (e.get("unrealized_pnl") or 0) < 0]
    no_data    = [e for e in enriched if e.get("current_price") is None]

    biggest_winner = max(enriched, key=lambda e: e.get("pnl_pct") or -999, default=None)
    biggest_loser  = min(enriched, key=lambda e: e.get("pnl_pct") or 999, default=None)

    return {
        "total_invested":       round(total_invested, 0),
        "total_current_value":  round(total_current_value, 0),
        "total_unrealized_pnl": round(total_unrealized_pnl, 0),
        "total_pnl_pct":        round(total_pnl_pct, 2),
        "num_holdings":         len(holdings),
        "num_profitable":       len(profitable),
        "num_losing":           len(losing),
        "num_no_data":          len(no_data),
        "biggest_winner":       biggest_winner.get("symbol_short") if biggest_winner else None,
        "biggest_winner_pct":   biggest_winner.get("pnl_pct") if biggest_winner else None,
        "biggest_loser":        biggest_loser.get("symbol_short") if biggest_loser else None,
        "biggest_loser_pct":    biggest_loser.get("pnl_pct") if biggest_loser else None,
        "enriched_holdings":    enriched,
        "price_note":           "Yahoo Finance — Delayed (~15-20 min)",
    }
