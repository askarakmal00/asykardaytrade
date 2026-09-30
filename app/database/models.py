from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, UniqueConstraint, Text
from sqlalchemy.orm import relationship
import datetime

from app.database.connection import Base

class Symbol(Base):
    __tablename__ = "symbols"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, index=True, nullable=False)
    name = Column(String)
    sector = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    daily_prices = relationship("DailyPrice", back_populates="symbol_data", cascade="all, delete-orphan")
    intraday_prices = relationship("IntradayPrice", back_populates="symbol_data", cascade="all, delete-orphan")
    signals = relationship("Signal", back_populates="symbol_data", cascade="all, delete-orphan")





class DailyPrice(Base):
    __tablename__ = "daily_prices"
    __table_args__ = (UniqueConstraint('symbol_id', 'date', name='uq_symbol_date'),)

    id = Column(Integer, primary_key=True, index=True)
    symbol_id = Column(Integer, ForeignKey("symbols.id"), nullable=False)
    date = Column(DateTime, nullable=False, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    symbol_data = relationship("Symbol", back_populates="daily_prices")


class IntradayPrice(Base):
    __tablename__ = "intraday_prices"
    __table_args__ = (UniqueConstraint('symbol_id', 'timestamp', 'interval', name='uq_symbol_intraday'),)

    id = Column(Integer, primary_key=True, index=True)
    symbol_id = Column(Integer, ForeignKey("symbols.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    interval = Column(String, nullable=False)  # e.g. '15m', '1h', '5m'
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    symbol_data = relationship("Symbol", back_populates="intraday_prices")


class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True)
    symbol_id = Column(Integer, ForeignKey("symbols.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    price = Column(Float)
    score = Column(Integer)
    grade = Column(String)  # 'A+', 'A', 'WATCH', 'LOW QUALITY', 'NO TRADE'
    setup = Column(String)  # 'PULLBACK', 'BREAKOUT', 'NONE'
    status = Column(String) # 'READY', 'WAIT_PULLBACK', 'WAIT_BREAKOUT', 'WATCH', 'NO_TRADE', 'SKIP'

    entry_low = Column(Float)
    entry_high = Column(Float)
    stop_loss = Column(Float)
    tp1 = Column(Float)
    tp2 = Column(Float)
    risk_reward = Column(Float)
    
    rsi = Column(Float)
    ema9 = Column(Float)
    ema21 = Column(Float)
    volume_ratio = Column(Float)
    est_value = Column(Float)

    reason = Column(Text)  # JSON or multi-line text explaining setup and checklist
    data_timestamp = Column(DateTime)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    symbol_data = relationship("Symbol", back_populates="signals")


class ScanRun(Base):
    __tablename__ = "scan_runs"

    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    symbols_scanned = Column(Integer, default=0)
    symbols_passed = Column(Integer, default=0)
    status = Column(String, default="running")  # 'running', 'completed', 'failed'
    error_count = Column(Integer, default=0)


class PortfolioHolding(Base):

    """
    Portfolio holding — posisi saham yang dimiliki user.

    Quantity menggunakan LOT (1 lot = 100 saham), sesuai konvensi BEI.
    Berdiri sendiri, tidak bergantung pada tabel Symbol agar user bisa
    input posisi meski saham belum ada di universe screener.

    Kalkulasi (tidak disimpan, dihitung on-the-fly):
        shares         = quantity_lots × 100
        invested       = shares × avg_buy_price
        current_value  = shares × current_price
        unrealized_pnl = current_value − invested
        pnl_pct        = unrealized_pnl / invested × 100
    """
    __tablename__ = "portfolio_holdings"

    id             = Column(Integer, primary_key=True, index=True)
    symbol         = Column(String, nullable=False, index=True)      # e.g. 'BBCA.JK'
    company_name   = Column(String, nullable=True)                   # Nama perusahaan (opsional)
    quantity_lots  = Column(Integer, nullable=False, default=1)      # Jumlah LOT (1 lot = 100 saham)
    avg_buy_price  = Column(Float, nullable=False)                   # Harga beli rata-rata per saham
    buy_date       = Column(String, nullable=False)                  # 'YYYY-MM-DD'

    # Risk management (opsional — user bisa mengisi atau tidak)
    target_price   = Column(Float, nullable=True)
    stop_loss_price= Column(Float, nullable=True)
    notes          = Column(Text, nullable=True)

    is_active      = Column(Boolean, default=True, nullable=False)   # Soft delete
    created_at     = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


