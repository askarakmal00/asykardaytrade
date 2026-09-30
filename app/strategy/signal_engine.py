import datetime
import pytz
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional

from app.strategy.support_resistance import find_support_resistance
from app.strategy.pullback import detect_pullback
from app.strategy.breakout import detect_breakout
from app.strategy.risk_management import calculate_trade_levels
from app import config

TZ_JAKARTA = pytz.timezone("Asia/Jakarta")

def determine_entry_validity(
    price: float,
    entry_low: float,
    entry_high: float,
    dist_ema9_pct: float,
    status: str,
    stop_loss: float
) -> str:
    """
    Evaluates whether the current price is currently in a valid actionable zone.
    Returns: 'VALID', 'MISSED', 'EXTENDED', 'INVALID', 'UNKNOWN'
    """
    if price <= 0 or entry_low <= 0 or entry_high <= 0:
        return "UNKNOWN"

    if status in ["NO_TRADE", "DATA_UNAVAILABLE"]:
        return "INVALID"

    if stop_loss > 0 and price <= stop_loss:
        return "INVALID"

    # Price has already surged past the entry zone (> 1.5% above entry_high)
    if price > entry_high * 1.015:
        return "MISSED"

    # Price is over-extended from dynamic support EMA9 (> 3.0%)
    if dist_ema9_pct > 3.0:
        return "EXTENDED"

    # Price is resting inside or acceptable retest near entry zone
    if entry_low * 0.985 <= price <= entry_high * 1.015:
        return "VALID"

    if status in ["WAIT_PULLBACK", "WAIT_BREAKOUT", "WATCH"]:
        return "VALID"

    return "VALID"

def determine_freshness(gen_time: Optional[datetime.datetime]) -> Dict[str, Any]:
    """
    Calculates signal age and freshness label: 'FRESH', 'AGING', 'STALE'
    Configurable via SIGNAL_FRESH_MINUTES and SIGNAL_AGING_MINUTES.
    """
    if not gen_time:
        now_jkt = datetime.datetime.now(TZ_JAKARTA)
        return {
            "freshness": "FRESH",
            "signal_age_minutes": 0,
            "signal_generated_at": now_jkt.isoformat(),
            "signal_generated_str": now_jkt.strftime("%d %b %Y %H:%M WIB")
        }

    now_jkt = datetime.datetime.now(TZ_JAKARTA)
    if gen_time.tzinfo is None:
        gen_jkt = TZ_JAKARTA.localize(gen_time)
    else:
        gen_jkt = gen_time.astimezone(TZ_JAKARTA)

    age_minutes = max(0, int((now_jkt - gen_jkt).total_seconds() / 60))

    if age_minutes <= config.SIGNAL_FRESH_MINUTES:
        freshness = "FRESH"
    elif age_minutes <= config.SIGNAL_AGING_MINUTES:
        freshness = "AGING"
    else:
        freshness = "STALE"

    return {
        "freshness": freshness,
        "signal_age_minutes": age_minutes,
        "signal_generated_at": gen_jkt.isoformat(),
        "signal_generated_str": gen_jkt.strftime("%d %b %Y %H:%M WIB")
    }

def determine_next_action(status: str, entry_validity: str, freshness: str) -> str:
    """
    Maps current signal state and execution condition into a concrete trader action.
    Returns: CONSIDER_ENTRY, WAIT_PULLBACK, WAIT_BREAKOUT, MONITOR, 
             DO_NOT_CHASE, WAIT_REENTRY, DO_NOT_ENTER, RECHECK_SIGNAL
    """
    if freshness == "STALE":
        return "RECHECK_SIGNAL"

    if entry_validity == "MISSED":
        return "DO_NOT_CHASE"

    if entry_validity == "EXTENDED":
        return "WAIT_REENTRY"

    if entry_validity == "INVALID" or status == "NO_TRADE":
        return "DO_NOT_ENTER"

    if status == "READY":
        if entry_validity == "VALID":
            return "CONSIDER_ENTRY"
        return "WAIT_REENTRY"

    if status == "WAIT_PULLBACK":
        return "WAIT_PULLBACK"

    if status == "WAIT_BREAKOUT":
        return "WAIT_BREAKOUT"

    if status == "WATCH":
        return "MONITOR"

    return "MONITOR"


def evaluate_signal(
    df: pd.DataFrame,
    reference_price: Optional[float] = None,
    signal_time: Optional[datetime.datetime] = None
) -> Dict[str, Any]:
    """
    Unified rule-based signal evaluation engine.
    Calculates technical score (0-100), classification grade, setup type, 
    risk-managed trade levels (Entry, SL, TP1, TP2, RR), execution status,
    entry validity, signal freshness, and concrete next actions.
    """
    if df.empty or len(df) < 5:
        now_jkt = datetime.datetime.now(TZ_JAKARTA)
        return {
            "score": 0,
            "grade": "NO TRADE",
            "setup": "NONE",
            "status": "DATA_UNAVAILABLE",
            "price": 0,
            "entry_low": 0,
            "entry_high": 0,
            "entry_zone": "-",
            "stop_loss": 0,
            "tp1": 0,
            "tp2": 0,
            "risk_reward": 0,
            "rsi": 0,
            "ema9": 0,
            "ema21": 0,
            "volume_ratio": 0,
            "est_value": 0,
            "dist_ema9_pct": 0,
            "support_zone": "-",
            "resistance_zone": "-",
            "why_this_stock": [],
            "why_not_ready": ["Insufficient historical data in local database."],
            "reason": "Insufficient historical data",
            "primary_reason": "Insufficient historical data to compute signal.",
            "entry_validity": "UNKNOWN",
            "freshness": "UNKNOWN",
            "signal_age_minutes": 0,
            "signal_generated_at": now_jkt.isoformat(),
            "signal_generated_str": now_jkt.strftime("%d %b %Y %H:%M WIB"),
            "next_action": "MONITOR"
        }

    latest = df.iloc[-1]
    price = float(latest['close'])
    high = float(latest['high'])
    low = float(latest['low'])
    volume = float(latest.get('volume', 0))
    
    ema9 = float(latest.get('EMA9', price))
    ema21 = float(latest.get('EMA21', price))
    ma20 = float(latest.get('MA20', price))
    ma50 = float(latest.get('MA50', price))
    ema21_slope = float(latest.get('EMA21_Slope', 0.0))
    dist_ema9_pct = float(latest.get('Dist_EMA9_Pct', ((price - ema9) / ema9) * 100.0 if ema9 > 0 else 0))
    
    rsi = float(latest.get('RSI14', 50.0))
    stoch_k = float(latest.get('Stoch_RSI_K', 50.0))
    stoch_d = float(latest.get('Stoch_RSI_D', 50.0))
    
    vol_ratio = float(latest.get('Volume_Ratio', 1.0))
    est_value = float(latest.get('Estimated_Value', price * volume))

    # 1. Support and Resistance Analysis
    sr_levels = find_support_resistance(df)

    # 2. Setup Detection
    pullback_res = detect_pullback(df, sr_levels)
    breakout_res = detect_breakout(df, sr_levels)

    if pullback_res["is_pullback"]:
        setup_type = "PULLBACK"
        setup_boost = pullback_res["score_boost"]
        prelim_status = pullback_res["status"]
    elif breakout_res["is_breakout"]:
        setup_type = "BREAKOUT"
        setup_boost = breakout_res["score_boost"]
        prelim_status = breakout_res["status"]
    else:
        setup_type = "NONE"
        setup_boost = 0
        prelim_status = "WATCH"

    # 3. Trade Levels & Risk Management
    trade_levels = calculate_trade_levels(df, setup_type, sr_levels)
    rr = trade_levels.get("risk_reward", 0.0)

    # 4. Scoring Engine (0 - 100)
    score = 0
    why_this_stock: List[str] = []
    why_not_ready: List[str] = []

    # --- A. TREND (Max 25) ---
    trend_score = 0
    if price > ema9:
        trend_score += 8
        why_this_stock.append("Price above EMA9 dynamic support")
    else:
        why_not_ready.append(f"Price below EMA9 ({price:,.0f} vs {ema9:,.0f})")

    if ema9 > ema21:
        trend_score += 8
        why_this_stock.append("Bullish moving average alignment (EMA9 > EMA21)")
    else:
        why_not_ready.append("EMA9 is below EMA21")

    if ema21_slope > 0:
        trend_score += 5
        why_this_stock.append("EMA21 slope is ascending (Upward trend strength)")

    if price > ma20 and ma20 > ma50:
        trend_score += 4
        why_this_stock.append("Daily trend context is Bullish (Close > MA20 > MA50)")
    
    score += min(25, trend_score)

    # --- B. MOMENTUM (Max 20) ---
    mom_score = 0
    if 50.0 <= rsi <= 70.0:
        mom_score += 10
        why_this_stock.append(f"RSI in optimal bullish momentum zone ({rsi:.1f})")
    elif rsi < 50.0:
        why_not_ready.append(f"RSI momentum weak ({rsi:.1f} < 50)")

    if rsi > 55.0 and rsi <= 72.0:
        mom_score += 5
        why_this_stock.append("Positive momentum acceleration")

    if stoch_k > stoch_d and stoch_k >= 20.0:
        mom_score += 5
        why_this_stock.append("Stochastic RSI bullish crossover / recovery")

    score += min(20, mom_score)

    # --- C. LIQUIDITY (Max 20) ---
    liq_score = 0
    if est_value >= config.MIN_VALUE:
        liq_score += 7
        why_this_stock.append(f"Estimated value Rp{est_value/1e9:.1f}B exceeds Rp10B threshold")
    else:
        why_not_ready.append(f"Estimated transaction value Rp{est_value/1e9:.1f}B is below Rp10B")

    if volume >= config.MIN_VOLUME:
        liq_score += 5
        why_this_stock.append(f"Transaction volume {volume/1e6:.1f}M shares > 1.0M threshold")
    
    if vol_ratio >= config.MIN_VOLUME_RATIO:
        liq_score += 8
        why_this_stock.append(f"Volume Ratio {vol_ratio:.2f}x above 20-day average")
    elif vol_ratio >= 1.0:
        liq_score += 4

    score += min(20, liq_score)

    # --- D. SETUP (Max 25) ---
    score += min(25, setup_boost)
    if setup_type == "PULLBACK":
        why_this_stock.extend(pullback_res.get("reasons", []))
    elif setup_type == "BREAKOUT":
        why_this_stock.extend(breakout_res.get("reasons", []))

    # --- E. RISK / REWARD (Max 10) ---
    if rr >= 2.0:
        score += 10
        why_this_stock.append(f"Attractive Risk/Reward ratio 1:{rr:.2f} (>= 2.0)")
    elif rr >= config.MIN_RISK_REWARD:
        score += 5
        why_this_stock.append(f"Acceptable Risk/Reward ratio 1:{rr:.2f} (>= 1.5)")
    else:
        why_not_ready.append(f"Risk/Reward 1:{rr:.2f} below minimum 1:1.5 requirement")

    # --- F. PENALTIES ---
    if rsi > 75.0:
        score -= 10
        why_not_ready.append(f"Extreme overbought condition (RSI {rsi:.1f} > 75)")
    elif rsi > 70.0:
        why_not_ready.append(f"Overbought caution (RSI {rsi:.1f} > 70)")

    if dist_ema9_pct > 5.0:
        score -= 20
        why_not_ready.append(f"Severely extended from EMA9 (+{dist_ema9_pct:.1f}% > 5.0%)")
    elif dist_ema9_pct > 3.0:
        score -= 10
        why_not_ready.append(f"Extended from EMA9 (+{dist_ema9_pct:.1f}% > 3.0%)")

    if est_value < 5_000_000_000 or volume < 500_000:
        score -= 20
        why_not_ready.append("Low liquidity penalty")

    final_score = max(0, min(100, score))

    # 5. Signal Classification (Grade)
    if final_score >= 85:
        grade = "A+"
    elif final_score >= 75:
        grade = "A"
    elif final_score >= 65:
        grade = "WATCH"
    elif final_score >= 50:
        grade = "LOW QUALITY"
    else:
        grade = "NO TRADE"

    # 6. Final Status Resolution (SINGLE SOURCE OF TRUTH: config.MIN_SIGNAL_SCORE)
    if dist_ema9_pct > 5.0:
        status = "WAIT_PULLBACK"
    elif rr < config.MIN_RISK_REWARD and setup_type != "NONE":
        status = "NO_TRADE"
    elif prelim_status == "READY" and final_score >= config.MIN_SIGNAL_SCORE:
        status = "READY"
    elif prelim_status in ["WAIT_PULLBACK", "WAIT_BREAKOUT"]:
        status = prelim_status
    elif final_score >= 65:
        status = "WATCH"
    else:
        status = "NO_TRADE"

    # 7. Entry Validity & Dynamic Assessment
    entry_low = float(trade_levels.get("entry_low", price))
    entry_high = float(trade_levels.get("entry_high", price))
    stop_loss = float(trade_levels.get("stop_loss", price * 0.96))
    tp1 = float(trade_levels.get("tp1", price * 1.04))
    tp2 = float(trade_levels.get("tp2", price * 1.08))

    eval_price = float(reference_price) if reference_price is not None and reference_price > 0 else price
    entry_val = determine_entry_validity(
        price=eval_price,
        entry_low=entry_low,
        entry_high=entry_high,
        dist_ema9_pct=dist_ema9_pct,
        status=status,
        stop_loss=stop_loss
    )

    # 8. Signal Freshness
    freshness_info = determine_freshness(signal_time)

    # 9. Next Action
    next_action = determine_next_action(
        status=status,
        entry_validity=entry_val,
        freshness=freshness_info["freshness"]
    )

    # 10. Primary Reason (Direct, non-generic summary for trader)
    if status == "READY":
        if setup_type == "PULLBACK":
            primary_reason = f"Bullish pullback setup near EMA9/EMA21 dynamic support with favorable 1:{rr:.1f} Risk/Reward."
        elif setup_type == "BREAKOUT":
            primary_reason = f"Consolidation breakout confirmed with {vol_ratio:.1f}x volume surge near resistance."
        else:
            primary_reason = f"Solid trend alignment and momentum with acceptable 1:{rr:.1f} Risk/Reward."
    elif status == "WAIT_PULLBACK":
        primary_reason = f"Valid pullback setup, but price is extended (+{dist_ema9_pct:.1f}% from EMA9) — wait for entry zone."
    elif status == "WAIT_BREAKOUT":
        primary_reason = "Price is testing key resistance level — wait for breakout candle and volume confirmation."
    elif status == "WATCH":
        primary_reason = "Setup is developing with decent momentum, but has not triggered all entry checklist criteria."
    elif status == "NO_TRADE":
        if why_not_ready:
            primary_reason = f"Do not enter: {why_not_ready[0]}."
        else:
            primary_reason = "Criteria not met for day trade entry."
    else:
        primary_reason = "Signal pending technical review."

    reason_summary = "\n".join([f"✓ {item}" for item in why_this_stock] + [f"✗ {item}" for item in why_not_ready])

    return {
        "score": final_score,
        "grade": grade,
        "setup": setup_type,
        "status": status,
        "price": price,
        "entry_low": entry_low,
        "entry_high": entry_high,
        "entry_zone": trade_levels.get("entry_zone", f"{price:,.0f}"),
        "stop_loss": stop_loss,
        "tp1": tp1,
        "tp2": tp2,
        "risk_reward": rr,
        "rsi": rsi,
        "ema9": ema9,
        "ema21": ema21,
        "volume_ratio": vol_ratio,
        "est_value": est_value,
        "dist_ema9_pct": dist_ema9_pct,
        "support_zone": sr_levels.get("support_zone", "-"),
        "resistance_zone": sr_levels.get("resistance_zone", "-"),
        "why_this_stock": why_this_stock,
        "why_not_ready": why_not_ready,
        "reason": reason_summary,
        "primary_reason": primary_reason,
        "entry_validity": entry_val,
        "freshness": freshness_info["freshness"],
        "signal_age_minutes": freshness_info["signal_age_minutes"],
        "signal_generated_at": freshness_info["signal_generated_at"],
        "signal_generated_str": freshness_info["signal_generated_str"],
        "next_action": next_action
    }


def evaluate_signal_from_scanner(scanner_row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluasi sinyal menggunakan indikator pre-computed dari TradingView Scanner.

    Cocok untuk semua 891 saham IDX tanpa memerlukan data historis OHLCV.
    Menggunakan: RSI, EMA9, EMA20, EMA50, ATR, volume, avg_vol_30d,
                 support (Pivot S1), resistance (Pivot R1) dari TradingView.

    Args:
        scanner_row: dict dari fetch_all_scanner_data() atau fetch_scanner_single()
            {
                'open','high','low','close','volume','change_pct','change_abs',
                'rsi','ema9','ema20','ema50','ma20','ma50','atr',
                'avg_vol_30d','support','resistance'
            }

    Returns: dict dengan format SAMA dengan evaluate_signal() — kompatibel penuh.
    """
    now_jkt = datetime.datetime.now(TZ_JAKARTA)

    # ── Ambil nilai dari scanner row ─────────────────────────────────────────
    price      = float(scanner_row.get("close", 0))
    open_p     = float(scanner_row.get("open",  price))
    high_p     = float(scanner_row.get("high",  price))
    low_p      = float(scanner_row.get("low",   price))
    volume     = float(scanner_row.get("volume", 0))

    rsi        = float(scanner_row.get("rsi",    50.0))
    ema9       = float(scanner_row.get("ema9",   price))
    ema20      = float(scanner_row.get("ema20",  price))  # TV EMA20 ≈ EMA21
    ema50      = float(scanner_row.get("ema50",  price))
    ma20       = float(scanner_row.get("ma20",   price))
    ma50       = float(scanner_row.get("ma50",   price))
    atr        = float(scanner_row.get("atr",    price * 0.02))
    avg_vol    = float(scanner_row.get("avg_vol_30d", volume if volume > 0 else 1))
    support    = float(scanner_row.get("support",    price * 0.97))
    resistance = float(scanner_row.get("resistance", price * 1.03))

    # Guard: harga tidak valid
    if price <= 0:
        return {
            "score": 0, "grade": "NO TRADE", "setup": "NONE",
            "status": "DATA_UNAVAILABLE", "price": 0,
            "entry_low": 0, "entry_high": 0, "entry_zone": "-",
            "stop_loss": 0, "tp1": 0, "tp2": 0, "risk_reward": 0,
            "rsi": 0, "ema9": 0, "ema21": 0, "volume_ratio": 0,
            "est_value": 0, "dist_ema9_pct": 0,
            "support_zone": "-", "resistance_zone": "-",
            "why_this_stock": [], "why_not_ready": ["Harga tidak valid dari scanner."],
            "reason": "No valid price data",
            "primary_reason": "Data harga tidak tersedia dari TradingView Scanner.",
            "entry_validity": "UNKNOWN", "freshness": "FRESH",
            "signal_age_minutes": 0,
            "signal_generated_at": now_jkt.isoformat(),
            "signal_generated_str": now_jkt.strftime("%d %b %Y %H:%M WIB"),
            "next_action": "MONITOR"
        }

    # ── Derived values ───────────────────────────────────────────────────────
    dist_ema9_pct = ((price - ema9) / ema9 * 100.0) if ema9 > 0 else 0.0
    vol_ratio     = (volume / avg_vol) if avg_vol > 0 else 1.0
    est_value     = price * volume
    # EMA slope proxy: besar selisih EMA9 - EMA20 (positif = trend naik)
    ema_slope     = ema9 - ema20

    # ── Scoring (sama dengan evaluate_signal) ────────────────────────────────
    score = 0
    why_this_stock: List[str] = []
    why_not_ready: List[str]  = []

    # A. TREND (Max 25)
    trend_score = 0
    if price > ema9:
        trend_score += 8
        why_this_stock.append("Harga di atas EMA9 — dynamic support terjaga")
    else:
        why_not_ready.append(f"Harga di bawah EMA9 ({price:,.0f} vs {ema9:,.0f})")

    if ema9 > ema20:
        trend_score += 8
        why_this_stock.append("Alignment bullish (EMA9 > EMA20)")
    else:
        why_not_ready.append("EMA9 di bawah EMA20 — trend belum bullish")

    if ema_slope > 0:
        trend_score += 5
        why_this_stock.append("EMA20 slope positif — kekuatan trend naik")

    if price > ma20 and ma20 > ma50:
        trend_score += 4
        why_this_stock.append("Close > MA20 > MA50 — konteks trend harian bullish")

    score += min(25, trend_score)

    # B. MOMENTUM (Max 20)
    mom_score = 0
    if 50.0 <= rsi <= 70.0:
        mom_score += 10
        why_this_stock.append(f"RSI di zona momentum optimal ({rsi:.1f})")
    elif rsi < 50.0:
        why_not_ready.append(f"RSI lemah ({rsi:.1f} < 50)")

    if 55.0 < rsi <= 72.0:
        mom_score += 5
        why_this_stock.append("Akselerasi momentum positif")

    score += min(20, mom_score)

    # C. LIQUIDITY (Max 20)
    liq_score = 0
    if est_value >= config.MIN_VALUE:
        liq_score += 7
        why_this_stock.append(f"Nilai transaksi Rp{est_value/1e9:.1f}B > Rp10B")
    else:
        why_not_ready.append(f"Nilai transaksi Rp{est_value/1e9:.1f}B < Rp10B (likuiditas rendah)")

    if volume >= config.MIN_VOLUME:
        liq_score += 5
        why_this_stock.append(f"Volume {volume/1e6:.1f}M lembar > 1.0M threshold")

    if vol_ratio >= config.MIN_VOLUME_RATIO:
        liq_score += 8
        why_this_stock.append(f"Volume Ratio {vol_ratio:.2f}x di atas rata-rata 30 hari")
    elif vol_ratio >= 1.0:
        liq_score += 4

    score += min(20, liq_score)

    # D. SETUP DETECTION (Max 25) — tanpa historical series, pakai scanner indicators
    setup_type = "NONE"
    setup_boost = 0
    prelim_status = "WATCH"

    trend_bullish = price >= ema9 * 0.985 and ema9 >= ema20 * 0.99
    near_support   = price <= ema9 * 1.025  # harga dekat EMA9 (< 2.5% di atas)
    momentum_ok    = 45.0 <= rsi <= 68.0
    near_resistance = price >= resistance * 0.97
    vol_surge       = vol_ratio >= 1.4

    # Pullback setup: trend bullish, price dekat EMA9/support
    if trend_bullish and near_support and momentum_ok:
        setup_type = "PULLBACK"
        setup_boost = 15
        why_this_stock.append("Setup pullback valid — harga mendekati dynamic support EMA9")
        if momentum_ok:
            setup_boost += 5
            why_this_stock.append("Momentum pulih tanpa kondisi overbought")
        if dist_ema9_pct > 3.0:
            prelim_status = "WAIT_PULLBACK"
        else:
            prelim_status = "READY"

    # Breakout setup: price dekat resistance, volume surge
    elif near_resistance and vol_surge and price >= ema9:
        setup_type = "BREAKOUT"
        setup_boost = 15
        why_this_stock.append("Setup breakout near resistance dengan volume expansion")
        if vol_surge:
            setup_boost += 5
            why_this_stock.append(f"Volume surge {vol_ratio:.1f}x konfirmasi tekanan beli")
        prelim_status = "WAIT_BREAKOUT" if not (price >= resistance) else "READY"

    score += min(25, setup_boost)

    # E. RISK / REWARD (Max 10)
    # Entry zone
    if setup_type == "PULLBACK":
        entry_low  = round(min(price, max(ema20, ema9 * 0.995)), 0)
        entry_high = round(max(price, ema9 * 1.005), 0)
    elif setup_type == "BREAKOUT":
        entry_low  = round(price * 0.995, 0)
        entry_high = round(price * 1.005, 0)
    else:
        entry_low  = round(price * 0.99, 0)
        entry_high = round(price * 1.01, 0)

    if entry_low == entry_high:
        entry_low  = round(price * 0.995, 0)
        entry_high = round(price * 1.005, 0)

    # Stop loss: bawah support atau 1.5 ATR dari entry
    raw_sl   = min(support * 0.99, entry_low - 1.5 * atr)
    stop_loss = max(round(raw_sl, 0), round(price * 0.93, 0))  # max drawdown 7%
    if stop_loss >= entry_low:
        stop_loss = round(entry_low * 0.97, 0)

    risk_amount   = max(1.0, entry_high - stop_loss)
    tp1           = round(entry_high + risk_amount * 1.5, 0)
    tp2           = round(max(resistance, entry_high + risk_amount * 2.0), 0)
    reward_amount = tp1 - entry_high
    rr            = round(reward_amount / risk_amount, 2) if risk_amount > 0 else 0.0

    if rr >= 2.0:
        score += 10
        why_this_stock.append(f"Risk/Reward menarik 1:{rr:.2f} (≥ 2.0)")
    elif rr >= config.MIN_RISK_REWARD:
        score += 5
        why_this_stock.append(f"Risk/Reward acceptable 1:{rr:.2f} (≥ 1.5)")
    else:
        why_not_ready.append(f"Risk/Reward 1:{rr:.2f} di bawah minimum 1:1.5")

    # F. PENALTIES
    if rsi > 75.0:
        score -= 10
        why_not_ready.append(f"Overbought extreme (RSI {rsi:.1f} > 75)")
    elif rsi > 70.0:
        why_not_ready.append(f"Caution overbought (RSI {rsi:.1f} > 70)")

    if dist_ema9_pct > 5.0:
        score -= 20
        why_not_ready.append(f"Terlalu jauh dari EMA9 (+{dist_ema9_pct:.1f}% > 5.0%)")
    elif dist_ema9_pct > 3.0:
        score -= 10
        why_not_ready.append(f"Extended dari EMA9 (+{dist_ema9_pct:.1f}% > 3.0%)")

    if est_value < 5_000_000_000 or volume < 500_000:
        score -= 20
        why_not_ready.append("Penalti likuiditas rendah")

    # Price filter
    if price < config.MIN_PRICE:
        score -= 30
        why_not_ready.append(f"Harga Rp{price:,.0f} di bawah minimum Rp{config.MIN_PRICE:,}")

    final_score = max(0, min(100, score))

    # Classification
    if final_score >= 85:
        grade = "A+"
    elif final_score >= 75:
        grade = "A"
    elif final_score >= 65:
        grade = "WATCH"
    elif final_score >= 50:
        grade = "LOW QUALITY"
    else:
        grade = "NO TRADE"

    # Status
    if dist_ema9_pct > 5.0:
        status = "WAIT_PULLBACK"
    elif rr < config.MIN_RISK_REWARD and setup_type != "NONE":
        status = "NO_TRADE"
    elif prelim_status == "READY" and final_score >= config.MIN_SIGNAL_SCORE:
        status = "READY"
    elif prelim_status in ("WAIT_PULLBACK", "WAIT_BREAKOUT"):
        status = prelim_status
    elif final_score >= 65:
        status = "WATCH"
    else:
        status = "NO_TRADE"

    # Entry validity
    entry_val = determine_entry_validity(
        price=price, entry_low=entry_low, entry_high=entry_high,
        dist_ema9_pct=dist_ema9_pct, status=status, stop_loss=stop_loss
    )

    # Freshness
    freshness_info = determine_freshness(now_jkt)

    # Next action
    next_action = determine_next_action(status, entry_val, freshness_info["freshness"])

    # Primary reason
    if status == "READY":
        if setup_type == "PULLBACK":
            primary_reason = f"Setup pullback bullish ke EMA9 dengan R:R 1:{rr:.1f} yang menarik."
        elif setup_type == "BREAKOUT":
            primary_reason = f"Breakout dengan {vol_ratio:.1f}x volume surge dekat resistance."
        else:
            primary_reason = f"Trend dan momentum solid, R:R 1:{rr:.1f}."
    elif status == "WAIT_PULLBACK":
        primary_reason = f"Setup valid, tapi harga terlalu jauh (+{dist_ema9_pct:.1f}% dari EMA9) — tunggu pullback."
    elif status == "WAIT_BREAKOUT":
        primary_reason = "Harga menguji resistance — tunggu konfirmasi breakout dengan volume."
    elif status == "WATCH":
        primary_reason = "Setup berkembang, belum memenuhi semua kriteria entry."
    else:
        primary_reason = why_not_ready[0] if why_not_ready else "Kriteria entry belum terpenuhi."

    entry_zone_str = f"{int(entry_low)} – {int(entry_high)}" if entry_low >= 10 else f"{entry_low:.2f} – {entry_high:.2f}"
    support_zone   = f"{int(support * 0.99)} – {int(support * 1.01)}" if support >= 10 else f"{support:.2f}"
    resistance_zone = f"{int(resistance * 0.99)} – {int(resistance * 1.01)}" if resistance >= 10 else f"{resistance:.2f}"

    return {
        "score":      final_score,
        "grade":      grade,
        "setup":      setup_type,
        "status":     status,
        "price":      price,
        "entry_low":  entry_low,
        "entry_high": entry_high,
        "entry_zone": entry_zone_str,
        "stop_loss":  stop_loss,
        "tp1":        tp1,
        "tp2":        tp2,
        "risk_reward":    rr,
        "rsi":            rsi,
        "ema9":           ema9,
        "ema21":          ema20,          # alias EMA20 → ema21 field
        "volume_ratio":   round(vol_ratio, 3),
        "est_value":      est_value,
        "dist_ema9_pct":  round(dist_ema9_pct, 2),
        "support_zone":   support_zone,
        "resistance_zone": resistance_zone,
        "why_this_stock": why_this_stock,
        "why_not_ready":  why_not_ready,
        "reason":         "\n".join(
            [f"✓ {x}" for x in why_this_stock] +
            [f"✗ {x}" for x in why_not_ready]
        ),
        "primary_reason": primary_reason,
        "entry_validity": entry_val,
        "freshness":      freshness_info["freshness"],
        "signal_age_minutes":  freshness_info["signal_age_minutes"],
        "signal_generated_at": freshness_info["signal_generated_at"],
        "signal_generated_str": freshness_info["signal_generated_str"],
        "next_action":    next_action,
    }
