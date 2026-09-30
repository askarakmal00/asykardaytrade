import pandas as pd
import os
import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert

def _get_insert_fn(db: Session):
    try:
        if db.bind and db.bind.dialect.name == "postgresql":
            return pg_insert
    except Exception:
        pass
    return sqlite_insert

from app.database.models import Symbol, DailyPrice, IntradayPrice, Signal, ScanRun, PortfolioHolding





def get_active_symbols(db: Session) -> List[Symbol]:
    return db.query(Symbol).filter(Symbol.is_active == True).all()

def get_symbol_by_ticker(db: Session, ticker: str) -> Optional[Symbol]:
    return db.query(Symbol).filter(Symbol.symbol == ticker).first()

def get_symbol_by_id(db: Session, symbol_id: int) -> Optional[Symbol]:
    return db.query(Symbol).filter(Symbol.id == symbol_id).first()

def seed_symbols_from_csv(db: Session, csv_path: str = "data/idx_symbols.csv"):
    if not os.path.exists(csv_path):
        print(f"Warning: CSV file not found at {csv_path}")
        return

    df = pd.read_csv(csv_path)
    for _, row in df.iterrows():
        symbol_ticker = str(row['symbol']).strip()
        name = str(row.get('name', symbol_ticker)).strip()
        sector = str(row.get('sector', '')) if not pd.isna(row.get('sector')) else ''
        
        existing = get_symbol_by_ticker(db, symbol_ticker)
        if not existing:
            new_symbol = Symbol(symbol=symbol_ticker, name=name, sector=sector)
            db.add(new_symbol)
        else:
            existing.name = name
            if sector:
                existing.sector = sector
    
    db.commit()

def save_daily_prices(db: Session, symbol_id: int, df: pd.DataFrame):
    """
    Save pandas dataframe of prices to SQLite using upsert.
    Expects df with DatetimeIndex (timezone-aware, Asia/Jakarta) and
    columns: Open, High, Low, Close, Volume.

    IMPORTANT: We strip timezone before storing to avoid UTC shift bugs.
    The date is stored as the LOCAL (Asia/Jakarta) calendar date.
    """
    if df.empty:
        return

    records = []
    for date, row in df.iterrows():
        if pd.isna(row.get('Close')):
            continue

        # Extract the LOCAL calendar date (ignore time-of-day, strip timezone)
        # date here is a Timestamp (tz-aware). .date() gives the local calendar date.
        if hasattr(date, 'date'):
            local_date = date.date()  # e.g. datetime.date(2026, 8, 19)
        else:
            local_date = pd.to_datetime(date).date()

        # Store as naive midnight datetime for SQLite compatibility
        dt = datetime.datetime.combine(local_date, datetime.time.min)

        records.append({
            "symbol_id": symbol_id,
            "date": dt,
            "open":   float(row.get('Open',   0.0)),
            "high":   float(row.get('High',   0.0)),
            "low":    float(row.get('Low',    0.0)),
            "close":  float(row.get('Close',  0.0)),
            "volume": float(row.get('Volume', 0.0)) if not pd.isna(row.get('Volume', float('nan'))) else 0.0
        })

    if not records:
        return

    ins_fn = _get_insert_fn(db)
    stmt = ins_fn(DailyPrice).values(records)
    update_dict = {
        'open':   stmt.excluded.open,
        'high':   stmt.excluded.high,
        'low':    stmt.excluded.low,
        'close':  stmt.excluded.close,
        'volume': stmt.excluded.volume,
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=['symbol_id', 'date'],
        set_=update_dict
    )
    db.execute(stmt)
    db.commit()


def save_intraday_prices(db: Session, symbol_id: int, df: pd.DataFrame, interval: str = "15m"):
    """
    Save intraday candle data.
    """
    if df.empty:
        return

    records = []
    for ts, row in df.iterrows():
        if pd.isna(row.get('Close')):
            continue
        dt = ts.to_pydatetime() if hasattr(ts, 'to_pydatetime') else pd.to_datetime(ts).to_pydatetime()
        records.append({
            "symbol_id": symbol_id,
            "timestamp": dt,
            "interval": interval,
            "open": float(row.get('Open', 0.0)),
            "high": float(row.get('High', 0.0)),
            "low": float(row.get('Low', 0.0)),
            "close": float(row.get('Close', 0.0)),
            "volume": float(row.get('Volume', 0.0)) if not pd.isna(row.get('Volume')) else 0.0
        })

    if not records:
        return

    ins_fn = _get_insert_fn(db)
    stmt = ins_fn(IntradayPrice).values(records)
    update_dict = {
        'open': stmt.excluded.open,
        'high': stmt.excluded.high,
        'low': stmt.excluded.low,
        'close': stmt.excluded.close,
        'volume': stmt.excluded.volume,
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=['symbol_id', 'timestamp', 'interval'],
        set_=update_dict
    )
    db.execute(stmt)
    db.commit()

def get_recent_daily_prices(db: Session, symbol_id: int, limit: int = 250) -> List[DailyPrice]:
    return db.query(DailyPrice)\
        .filter(DailyPrice.symbol_id == symbol_id)\
        .order_by(DailyPrice.date.desc())\
        .limit(limit)\
        .all()

def get_all_daily_prices(db: Session, symbol_id: int, start_date: Optional[datetime.date] = None, end_date: Optional[datetime.date] = None) -> List[DailyPrice]:
    q = db.query(DailyPrice).filter(DailyPrice.symbol_id == symbol_id)
    if start_date:
        q = q.filter(DailyPrice.date >= start_date)
    if end_date:
        q = q.filter(DailyPrice.date <= end_date)
    return q.order_by(DailyPrice.date.asc()).all()

def get_recent_intraday_prices(db: Session, symbol_id: int, interval: str = "15m", limit: int = 200) -> List[IntradayPrice]:
    return db.query(IntradayPrice)\
        .filter(IntradayPrice.symbol_id == symbol_id, IntradayPrice.interval == interval)\
        .order_by(IntradayPrice.timestamp.desc())\
        .limit(limit)\
        .all()

def save_signal(db: Session, signal_data: Dict[str, Any]) -> Signal:
    sig = Signal(
        symbol_id=signal_data["symbol_id"],
        price=signal_data.get("price"),
        score=signal_data.get("score"),
        grade=signal_data.get("grade"),
        setup=signal_data.get("setup"),
        status=signal_data.get("status"),
        entry_low=signal_data.get("entry_low"),
        entry_high=signal_data.get("entry_high"),
        stop_loss=signal_data.get("stop_loss"),
        tp1=signal_data.get("tp1"),
        tp2=signal_data.get("tp2"),
        risk_reward=signal_data.get("risk_reward"),
        rsi=signal_data.get("rsi"),
        ema9=signal_data.get("ema9"),
        ema21=signal_data.get("ema21"),
        volume_ratio=signal_data.get("volume_ratio"),
        est_value=signal_data.get("est_value"),
        reason=signal_data.get("reason"),
        data_timestamp=signal_data.get("data_timestamp")
    )
    db.add(sig)
    db.commit()
    db.refresh(sig)
    return sig

def get_latest_signals(db: Session, limit: int = 50) -> List[Signal]:
    return db.query(Signal).order_by(Signal.timestamp.desc()).limit(limit).all()

def create_scan_run(db: Session) -> ScanRun:
    run = ScanRun(started_at=datetime.datetime.utcnow(), status="running")
    db.add(run)
    db.commit()
    db.refresh(run)
    return run

def complete_scan_run(db: Session, run_id: int, scanned: int, passed: int, errors: int = 0, status: str = "completed"):
    run = db.query(ScanRun).filter(ScanRun.id == run_id).first()
    if run:
        run.completed_at = datetime.datetime.utcnow()
        run.symbols_scanned = scanned
        run.symbols_passed = passed
        run.error_count = errors
        run.status = status
        db.commit()


# ============================================================
# ALIAS — get_symbol_by_name (alias for get_symbol_by_ticker)
# ============================================================

def get_symbol_by_name(db: Session, symbol: str) -> Optional[Symbol]:
    """Alias for get_symbol_by_ticker. Used by intraday modules."""
    return get_symbol_by_ticker(db, symbol)


# ============================================================
# PORTFOLIO HOLDINGS CRUD
# ============================================================


def get_all_holdings(db: Session) -> List[PortfolioHolding]:
    """Return semua posisi aktif (is_active=True), urut dari yang terbaru."""
    return (
        db.query(PortfolioHolding)
        .filter(PortfolioHolding.is_active == True)
        .order_by(PortfolioHolding.created_at.desc())
        .all()
    )


def get_holding_by_id(db: Session, holding_id: int) -> Optional[PortfolioHolding]:
    """Return satu posisi berdasarkan ID."""
    return (
        db.query(PortfolioHolding)
        .filter(PortfolioHolding.id == holding_id, PortfolioHolding.is_active == True)
        .first()
    )


def create_holding(db: Session, data: dict) -> Optional[PortfolioHolding]:
    """
    Buat posisi baru.

    data dict keys:
        symbol (str, required)       — e.g. 'BBCA' atau 'BBCA.JK'
        quantity_lots (int, required) — jumlah lot
        avg_buy_price (float, required) — harga beli rata-rata
        buy_date (str, required)     — 'YYYY-MM-DD'
        company_name (str, optional)
        target_price (float, optional)
        stop_loss_price (float, optional)
        notes (str, optional)
    """
    try:
        # Normalisasi symbol: tambahkan .JK jika belum ada
        sym = data.get("symbol", "").upper().strip()
        if sym and not sym.endswith(".JK") and "." not in sym:
            sym = f"{sym}.JK"

        holding = PortfolioHolding(
            symbol         = sym,
            company_name   = data.get("company_name"),
            quantity_lots  = int(data.get("quantity_lots", 1)),
            avg_buy_price  = float(data.get("avg_buy_price", 0)),
            buy_date       = str(data.get("buy_date", "")),
            target_price   = float(data["target_price"]) if data.get("target_price") else None,
            stop_loss_price= float(data["stop_loss_price"]) if data.get("stop_loss_price") else None,
            notes          = data.get("notes"),
            is_active      = True,
        )
        db.add(holding)
        db.commit()
        db.refresh(holding)
        return holding
    except Exception as e:
        db.rollback()
        import logging
        logging.getLogger("repositories").error(f"create_holding error: {e}")
        return None


def update_holding(db: Session, holding_id: int, data: dict) -> Optional[PortfolioHolding]:
    """
    Update posisi yang ada. Hanya field yang diberikan yang diupdate.
    """
    holding = get_holding_by_id(db, holding_id)
    if not holding:
        return None

    try:
        updatable = [
            "quantity_lots", "avg_buy_price", "buy_date",
            "company_name", "target_price", "stop_loss_price", "notes"
        ]
        for field in updatable:
            if field in data and data[field] is not None:
                val = data[field]
                if field == "quantity_lots":
                    val = int(val)
                elif field in ("avg_buy_price", "target_price", "stop_loss_price"):
                    val = float(val)
                setattr(holding, field, val)

        # Allow explicit null for optional price fields
        for field in ("target_price", "stop_loss_price", "notes", "company_name"):
            if field in data and data[field] == "":
                setattr(holding, field, None)

        holding.updated_at = datetime.datetime.utcnow()
        db.commit()
        db.refresh(holding)
        return holding
    except Exception as e:
        db.rollback()
        import logging
        logging.getLogger("repositories").error(f"update_holding error: {e}")
        return None


def delete_holding(db: Session, holding_id: int) -> bool:
    """
    Soft-delete posisi (is_active = False).
    Data tetap ada di database untuk keperluan history.
    """
    holding = get_holding_by_id(db, holding_id)
    if not holding:
        return False
    holding.is_active = False
    holding.updated_at = datetime.datetime.utcnow()
    db.commit()
    return True


