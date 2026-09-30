from fastapi import FastAPI, Request, Depends, BackgroundTasks, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
import os
import datetime
import math
import pytz
import pandas as pd
from typing import Optional

TZ_JAKARTA = pytz.timezone("Asia/Jakarta")

def _to_jakarta_str(ts) -> str:
    try:
        if hasattr(ts, 'tzinfo') and ts.tzinfo is not None:
            return ts.astimezone(TZ_JAKARTA).strftime("%Y-%m-%d %H:%M:%S WIB")
        return pytz.utc.localize(ts).astimezone(TZ_JAKARTA).strftime("%Y-%m-%d %H:%M:%S WIB")
    except Exception:
        return str(ts)

def _safe_float(v):
    """Return float or None — never NaN or Inf."""
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None

from app import config
from app.database.connection import engine, get_db
from app.database import models, repositories
from app.services import market_data, scanner_service, ai_analyst
from app.services import portfolio_service
from app.services import portfolio_ai_analyst
from app.backtest.engine import BacktestEngine




# Global state for scanner status and caching
latest_scan_data = {
    "top_10": [],
    "passed": [],
    "all": [],
    "scanned_count": 0,
    "passed_count": 0,
    "a_plus_count": 0,
    "a_count": 0,
    "watch_count": 0,
    "last_scan": None,
    "last_scan_wib": None,
}

scan_status = {
    "status": "idle",
    "last_update": "System ready. Click Update Market Data or Run Screener."
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database tables exist
    models.Base.metadata.create_all(bind=engine)
    # Seed symbols on startup
    db = next(get_db())
    try:
        repositories.seed_symbols_from_csv(db)
    except Exception as e:
        print(f"Startup symbol seeding note: {e}")
    finally:
        db.close()
    yield

app = FastAPI(title="IDX Day Trade Signal System", version="1.0.0", lifespan=lifespan)

# Setup templates and static
os.makedirs("app/static", exist_ok=True)
templates = Jinja2Templates(directory="app/templates")

def get_market_status_info() -> dict:
    now_wib = datetime.datetime.now(TZ_JAKARTA)
    weekday = now_wib.weekday()
    hour = now_wib.hour
    minute = now_wib.minute

    # IDX Trading hours: Mon - Fri (09:00 - 16:00 WIB)
    is_weekday = weekday < 5
    if is_weekday:
        if (9, 0) <= (hour, minute) <= (16, 0):
            is_open = True
            status_text = "OPEN"
            status_desc = "Regular IDX trading session is active (09:00 – 16:00 WIB)."
        elif (hour, minute) < (9, 0):
            is_open = False
            status_text = "PRE-MARKET"
            status_desc = "Market opens today at 09:00 WIB."
        else:
            is_open = False
            status_text = "CLOSED"
            status_desc = f"Session closed at 16:00 WIB. Signals shown below are based on latest available data."
    else:
        is_open = False
        status_text = "CLOSED (WEEKEND)"
        status_desc = "Weekend. Signals shown below are based on latest available data."

    return {
        "is_open": is_open,
        "status_text": status_text,
        "status_desc": status_desc,
        "current_time_wib": now_wib.strftime("%d %b %Y %H:%M WIB"),
        "today_str": now_wib.strftime("%d %b %Y")
    }

# ----------------- HTML Pages -----------------

@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    symbols = repositories.get_active_symbols(db)
    total_symbols = len(symbols)
    
    # If no scan run yet, try running scanner once in memory or use cached
    global latest_scan_data
    if not latest_scan_data["all"]:
        try:
            latest_scan_data = scanner_service.run_scanner(db)
        except Exception as e:
            print(f"Initial scan note: {e}")

    market_info = get_market_status_info()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "total_symbols": total_symbols,
            "scan_results": latest_scan_data.get("ready_candidates", latest_scan_data.get("top_10", [])),
            "ready_candidates": latest_scan_data.get("ready_candidates", []),
            "wait_candidates": latest_scan_data.get("wait_candidates", []),
            "watch_candidates": latest_scan_data.get("watch_candidates", []),
            "no_trade_candidates": latest_scan_data.get("no_trade_candidates", []),
            "stats": latest_scan_data,
            "scan_status": scan_status,
            "market_info": market_info,
            "min_signal_score": config.MIN_SIGNAL_SCORE
        }
    )


@app.get("/screener", response_class=HTMLResponse)
def screener_page(request: Request, db: Session = Depends(get_db)):
    global latest_scan_data
    if not latest_scan_data["all"]:
        try:
            latest_scan_data = scanner_service.run_scanner(db)
        except Exception as e:
            print(f"Screener load note: {e}")

    return templates.TemplateResponse(
        request=request,
        name="screener.html",
        context={
            "all_candidates": latest_scan_data.get("all", []),
            "scan_status": scan_status
        }
    )

@app.get("/stock/{symbol}", response_class=HTMLResponse)
def stock_detail_page(symbol: str, request: Request, db: Session = Depends(get_db)):
    stock = scanner_service.process_symbol_detail(db, symbol.upper())
    if not stock:
        # Try with .JK suffix if omitted
        stock = scanner_service.process_symbol_detail(db, f"{symbol.upper()}.JK")
        
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found in database universe.")

    # Calculate fast per-stock historical backtest (takes ~0.02s)
    engine_bt = BacktestEngine(db, max_hold_days=5)
    bt_results = engine_bt.run(selected_symbols=[stock["symbol"]], setup_filter="ALL", min_score=70)

    return templates.TemplateResponse(
        request=request,
        name="stock_detail.html",
        context={
            "stock": stock,
            "backtest": bt_results
        }
    )

@app.get("/backtest", response_class=HTMLResponse)
def backtest_page(
    request: Request,
    symbol: Optional[str] = None,
    setup: str = "ALL",
    min_score: int = 70,
    max_hold: int = 5,
    db: Session = Depends(get_db)
):
    global latest_scan_data
    symbols_list = repositories.get_active_symbols(db)
    ready_symbols = [r["symbol"] for r in latest_scan_data.get("ready_candidates", [])]
    
    # Target symbol selection
    # Default to TOP_READY or first symbol for instant page load
    target_symbol = symbol if symbol is not None else ("TOP_READY" if ready_symbols else (symbols_list[0].symbol if symbols_list else "ALL"))
    
    selected_syms = None
    if target_symbol == "TOP_READY":
        selected_syms = ready_symbols if ready_symbols else [s.symbol for s in symbols_list[:18]]
    elif target_symbol == "ALL":
        selected_syms = None
    elif target_symbol:
        sym_clean = target_symbol.upper().strip()
        if not sym_clean.endswith(".JK") and "." not in sym_clean:
            sym_clean = f"{sym_clean}.JK"
        selected_syms = [sym_clean]

    engine_bt = BacktestEngine(db, max_hold_days=max_hold)
    results = engine_bt.run(
        selected_symbols=selected_syms,
        setup_filter=setup,
        min_score=min_score
    )

    return templates.TemplateResponse(
        request=request,
        name="backtest.html",
        context={
            "results": results,
            "selected_symbol": target_symbol,
            "selected_setup": setup,
            "min_score": min_score,
            "max_hold": max_hold,
            "all_symbols": symbols_list,
            "ready_symbols": ready_symbols
        }
    )

# ----------------- Debug Endpoints -----------------

@app.get("/debug/market-data/{symbol}", response_class=HTMLResponse)
def debug_market_data(symbol: str, request: Request):
    """Complete market data audit page for a given symbol."""
    import yfinance as yf
    from app.providers.yahoo import YahooFinanceProvider

    sym = symbol.upper()
    provider = YahooFinanceProvider()
    now_wib = datetime.datetime.now(TZ_JAKARTA)

    def _build_rows(df: pd.DataFrame, limit: int = 10):
        rows = []
        tail = df.tail(limit)
        for idx, row in tail.iterrows():
            rows.append({
                "timestamp_wib": _to_jakarta_str(idx),
                "open": _safe_float(row.get("Open")),
                "high": _safe_float(row.get("High")),
                "low": _safe_float(row.get("Low")),
                "close": _safe_float(row.get("Close")),
                "volume": int(row.get("Volume", 0)) if not pd.isna(row.get("Volume", float('nan'))) else 0,
            })
        return rows

    def _candle_meta(df: pd.DataFrame, interval_minutes: int):
        if df.empty:
            return {"last_timestamp_wib": "N/A", "last_close": None, "is_complete": "N/A"}
        last_ts = df.index[-1]
        last_ts_wib = last_ts.astimezone(TZ_JAKARTA)
        delta_min = (now_wib - last_ts_wib).total_seconds() / 60
        is_complete = delta_min > (interval_minutes * 1.1)
        return {
            "last_timestamp_wib": _to_jakarta_str(last_ts),
            "last_close": _safe_float(df["Close"].iloc[-1]),
            "is_complete": "YES" if is_complete else "POSSIBLY FORMING",
        }

    # Fetch quote
    quote = provider.get_quote(sym)

    # Fetch daily
    df_daily = provider.get_daily_data(sym, period="15d")
    daily_rows = _build_rows(df_daily)
    daily_meta = _candle_meta(df_daily, 1440)
    daily_meta["rows"] = daily_rows
    daily_meta["last_close"] = _safe_float(df_daily["Close"].iloc[-1]) if not df_daily.empty else None

    # Fetch 1H
    df_h1 = provider.get_intraday_data(sym, interval="1h", period="5d")
    h1_rows = _build_rows(df_h1)
    h1_meta = _candle_meta(df_h1, 60)
    h1_meta["rows"] = h1_rows

    # Fetch 15M
    df_m15 = provider.get_intraday_data(sym, interval="15m", period="5d")
    m15_rows = _build_rows(df_m15)
    m15_meta = _candle_meta(df_m15, 15)
    m15_meta["rows"] = m15_rows

    # Discrepancy explanation
    current_price = quote.get("current_price")
    prev_close = quote.get("previous_close")
    daily_close = daily_meta["last_close"]

    if current_price and prev_close and daily_close:
        diff = current_price - prev_close
        diff_pct = (diff / prev_close * 100) if prev_close else 0
        explanation = (
            f"The application previously showed daily_ohlcv['Close'].iloc[-1] = Rp {daily_close:,.0f} "
            f"(previous session close, labeled as 'Current Price' — INCORRECT). "
            f"The real current price is fast_info.last_price = Rp {current_price:,.0f}. "
            f"Previous close (yesterday) = Rp {prev_close:,.0f}. "
            f"Today's price change = {diff:+,.0f} ({diff_pct:+.2f}%). "
            f"Yahoo Finance daily candle for today's session may appear as NaN until session closes."
        )
    else:
        explanation = "Unable to compute discrepancy — one or more price sources returned None."

    # Market state heuristic (IDX: 09:00–16:00 WIB, Mon-Fri)
    weekday = now_wib.weekday()
    hour = now_wib.hour
    minute = now_wib.minute
    is_trading_hours = (weekday < 5) and ((9, 0) <= (hour, minute) <= (16, 0))
    market_state = "REGULAR" if is_trading_hours else "CLOSED"

    audit = {
        "system_time_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "system_time_wib": now_wib.strftime("%Y-%m-%d %H:%M:%S WIB"),
        "market_state": market_state,
        "data_note": "Yahoo Finance data is delayed ~15-20 min. Not guaranteed real-time.",
        "quote": quote,
        "daily": daily_meta,
        "h1": h1_meta,
        "m15": m15_meta,
        "discrepancy_explanation": explanation,
    }

    return templates.TemplateResponse(
        request=request,
        name="debug_market_data.html",
        context={"symbol": sym, "audit": audit}
    )

# ----------------- API Endpoints -----------------

@app.post("/api/update-data")
def update_data_endpoint(background_tasks: BackgroundTasks):
    def task():
        global scan_status, latest_scan_data
        scan_status["status"] = "downloading"
        scan_status["last_update"] = "Starting fast batch download from Yahoo Finance..."
        try:
            def progress(processed, total, info, step):
                scan_status["last_update"] = f"Downloading [{processed}/{total}] ({info})..."

            db_bg = next(get_db())
            res = market_data.update_market_data(db_bg, progress_callback=progress)
            
            # Automatically run scanner after fresh data download
            scan_status["status"] = "scanning"
            scan_status["last_update"] = "Data updated. Computing technical indicators and strategy setups..."
            latest_scan_data = scanner_service.run_scanner(db_bg)
            
            db_bg.close()
            scan_status["status"] = "idle"
            scan_status["last_update"] = f"Update complete. Found {latest_scan_data['ready_count']} Ready to Action signals ({latest_scan_data['a_plus_count']} A+, {latest_scan_data['a_count']} A) from {latest_scan_data['scanned_count']} stocks."
        except Exception as e:
            scan_status["status"] = "error"
            scan_status["last_update"] = f"Error during update: {e}"

    background_tasks.add_task(task)
    return {"message": "Market data update initiated in background"}

@app.post("/api/run-scanner")
def run_scanner_endpoint(background_tasks: BackgroundTasks):
    def task():
        global scan_status, latest_scan_data
        scan_status["status"] = "scanning"
        scan_status["last_update"] = "Evaluating trend, momentum, setups, and trade parameters..."
        try:
            db_bg = next(get_db())
            latest_scan_data = scanner_service.run_scanner(db_bg)
            db_bg.close()
            scan_status["status"] = "idle"
            scan_status["last_update"] = f"Scan complete. Found {latest_scan_data['ready_count']} Ready to Action signals ({latest_scan_data['a_plus_count']} A+, {latest_scan_data['a_count']} A) from {latest_scan_data['scanned_count']} stocks."
        except Exception as e:
            scan_status["status"] = "error"
            scan_status["last_update"] = f"Error during scanner execution: {e}"

    background_tasks.add_task(task)
    return {"message": "Scanner started in background"}

@app.get("/api/status")
def get_status():
    return scan_status

@app.get("/api/stock-data/{symbol}")
def get_stock_data(symbol: str, db: Session = Depends(get_db)):
    stock = scanner_service.process_symbol_detail(db, symbol.upper())
    if not stock:
        stock = scanner_service.process_symbol_detail(db, f"{symbol.upper()}.JK")
    if not stock:
        raise HTTPException(status_code=404, detail="Stock data not found")
    return stock

# ----------------- AI Endpoints -----------------

@app.get("/api/ai-analysis/{symbol}")
async def get_ai_analysis(symbol: str, db: Session = Depends(get_db)):
    """
    Analisis AI untuk saham menggunakan Google Gemini API (Free Tier).
    Dipanggil via AJAX dari halaman detail saham setelah page load.
    Returns JSON dengan ringkasan AI, confidence score, rekomendasi, dan risiko.
    """
    sym = symbol.upper()
    if not sym.endswith(".JK") and "." not in sym:
        sym = f"{sym}.JK"

    stock = scanner_service.process_symbol_detail(db, sym)
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")

    result = await ai_analyst.analyze_stock(stock)

    if result is None:
        return JSONResponse(
            status_code=503,
            content={
                "error": "ai_disabled",
                "message": "Fitur AI dinonaktifkan (AI_ENABLED=false di .env).",
            }
        )

    # If result contains error dict (e.g. missing API key)
    if "error" in result:
        return JSONResponse(status_code=200, content=result)

    return JSONResponse(content=result)


@app.get("/api/ai-status")
async def get_ai_status():
    """Cek status konfigurasi Google Gemini API."""
    status = await ai_analyst.check_gemini_status()
    return JSONResponse(content=status)


# ============================================================
# PORTFOLIO MANAGEMENT — HTML Routes
# ============================================================


@app.get("/portfolio", response_class=HTMLResponse)
def portfolio_dashboard(request: Request, db: Session = Depends(get_db)):
    """Halaman utama Portfolio Management."""
    return templates.TemplateResponse(
        request=request,
        name="portfolio.html",
        context={"active_page": "portfolio"}
    )


@app.get("/portfolio/{holding_id}", response_class=HTMLResponse)
def portfolio_detail_page(request: Request, holding_id: int, db: Session = Depends(get_db)):
    """Halaman detail satu posisi portfolio."""
    holding = repositories.get_holding_by_id(db, holding_id)
    if not holding:
        return HTMLResponse("<h3>Posisi tidak ditemukan.</h3>", status_code=404)

    enriched = portfolio_service.enrich_holding(db, holding)
    return templates.TemplateResponse(
        request=request,
        name="portfolio_detail.html",
        context={
            "active_page": "portfolio",
            "holding":     enriched,
        }
    )


# ============================================================
# PORTFOLIO MANAGEMENT — REST API
# ============================================================

@app.get("/api/portfolio")
def api_get_portfolio(db: Session = Depends(get_db)):
    """Return semua posisi portfolio aktif (dengan P/L + harga terkini)."""
    try:
        summary = portfolio_service.get_portfolio_summary(db)
        return JSONResponse(content={
            "holdings":  summary["enriched_holdings"],
            "summary":   {k: v for k, v in summary.items() if k != "enriched_holdings"},
            "count":     summary["num_holdings"],
            "price_note": summary["price_note"],
        })
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/portfolio/summary")
def api_portfolio_summary(db: Session = Depends(get_db)):
    """Return portfolio summary tanpa detail holdings."""
    try:
        summary = portfolio_service.get_portfolio_summary(db)
        return JSONResponse(content={
            k: v for k, v in summary.items() if k != "enriched_holdings"
        })
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.post("/api/portfolio")
async def api_create_holding(request: Request, db: Session = Depends(get_db)):
    """
    Tambah posisi baru ke portfolio.

    Body JSON (required):
        symbol, quantity_lots, avg_buy_price, buy_date

    Body JSON (optional):
        company_name, target_price, stop_loss_price, notes
    """
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(content={"error": "Invalid JSON body"}, status_code=400)

    # Validasi required fields
    errors = []
    if not data.get("symbol"):
        errors.append("symbol wajib diisi")
    if not data.get("quantity_lots") or int(data.get("quantity_lots", 0)) <= 0:
        errors.append("quantity_lots harus > 0")
    if not data.get("avg_buy_price") or float(data.get("avg_buy_price", 0)) <= 0:
        errors.append("avg_buy_price harus > 0")
    if not data.get("buy_date"):
        errors.append("buy_date wajib diisi (format YYYY-MM-DD)")
    if errors:
        return JSONResponse(content={"error": "; ".join(errors)}, status_code=422)

    holding = repositories.create_holding(db, data)
    if not holding:
        return JSONResponse(content={"error": "Gagal menyimpan posisi"}, status_code=500)

    return JSONResponse(
        content={"message": "Posisi berhasil ditambahkan", "id": holding.id},
        status_code=201
    )


@app.get("/api/portfolio/{holding_id}")
def api_get_holding(holding_id: int, db: Session = Depends(get_db)):
    """Return detail satu posisi + enrichment data."""
    holding = repositories.get_holding_by_id(db, holding_id)
    if not holding:
        return JSONResponse(content={"error": "Posisi tidak ditemukan"}, status_code=404)

    enriched = portfolio_service.enrich_holding(db, holding)
    return JSONResponse(content=enriched)


@app.put("/api/portfolio/{holding_id}")
async def api_update_holding(holding_id: int, request: Request, db: Session = Depends(get_db)):
    """Update posisi yang ada (partial update — hanya field yang dikirim)."""
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(content={"error": "Invalid JSON body"}, status_code=400)

    updated = repositories.update_holding(db, holding_id, data)
    if not updated:
        return JSONResponse(content={"error": "Posisi tidak ditemukan atau gagal diupdate"}, status_code=404)

    return JSONResponse(content={"message": "Posisi berhasil diupdate", "id": updated.id})


@app.delete("/api/portfolio/{holding_id}")
def api_delete_holding(holding_id: int, db: Session = Depends(get_db)):
    """Hapus posisi (soft delete — data tetap di DB)."""
    success = repositories.delete_holding(db, holding_id)
    if not success:
        return JSONResponse(content={"error": "Posisi tidak ditemukan"}, status_code=404)
    return JSONResponse(content={"message": "Posisi berhasil dihapus"})


@app.post("/api/portfolio/ai-analysis")
async def api_portfolio_ai_analysis(db: Session = Depends(get_db)):
    """
    AI analysis untuk seluruh portfolio (on-demand).

    Returns:
        portfolio_score, health_status, summary, per-stock actions,
        concentration risk, suggestions
    """
    if not config.AI_ENABLED:
        return JSONResponse(content={
            "ai_available": False,
            "message": "AI tidak aktif. Set AI_ENABLED=true di .env"
        })

    try:
        summary = portfolio_service.get_portfolio_summary(db)
        enriched = summary["enriched_holdings"]

        if not enriched:
            return JSONResponse(content={
                "ai_available": True,
                "portfolio_score": 0,
                "health_status": "INSUFFICIENT_DATA",
                "summary": "Portfolio kosong. Tambahkan posisi terlebih dahulu.",
            })

        result = await portfolio_ai_analyst.analyze_portfolio(enriched, summary)
        return JSONResponse(content=result)

    except Exception as e:
        return JSONResponse(content={
            "ai_available": False,
            "error": str(e),
            "message": "AI Portfolio analysis gagal — coba lagi."
        }, status_code=500)


@app.post("/api/portfolio/{holding_id}/ai-analysis")
async def api_holding_ai_analysis(holding_id: int, db: Session = Depends(get_db)):
    """
    AI analysis untuk satu posisi (on-demand).

    Returns:
        action, confidence, summary, reason, risk, suggested_action, suggested_sl/tp
    """
    if not config.AI_ENABLED:
        return JSONResponse(content={
            "ai_available": False,
            "message": "AI tidak aktif. Set AI_ENABLED=true di .env"
        })

    holding = repositories.get_holding_by_id(db, holding_id)
    if not holding:
        return JSONResponse(content={"error": "Posisi tidak ditemukan"}, status_code=404)

    try:
        enriched = portfolio_service.enrich_holding(db, holding)
        result   = await portfolio_ai_analyst.analyze_position(enriched)
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(content={
            "ai_available": False,
            "error": str(e),
            "message": "AI analysis gagal — coba lagi."
        }, status_code=500)


