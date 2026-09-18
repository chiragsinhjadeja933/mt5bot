"""
Database Models & Setup — Section 24 [ADD]
SQLAlchemy 2.x. NUMERIC for money. UTC timestamps. Portable SQLite/PostgreSQL.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, Numeric, String, Text,
    UniqueConstraint, Index, ForeignKey, create_engine, event,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship
from sqlalchemy.pool import StaticPool

import structlog

log = structlog.get_logger(__name__)


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Tables ────────────────────────────────────────────────────────────────────

class BotStateRow(Base):
    """Singleton row — persisted state across restarts."""
    __tablename__ = "bot_state"

    id: int = Column(Integer, primary_key=True, default=1)
    connection_state: str = Column(String(32), nullable=False, default="DISCONNECTED")
    bot_state: str = Column(String(32), nullable=False, default="READY")
    execution_mode: str = Column(String(32), nullable=False, default="DRY_RUN")
    emergency_stop: bool = Column(Boolean, nullable=False, default=False)
    confirmed_login: Optional[int] = Column(Integer, nullable=True)
    confirmed_server: Optional[str] = Column(String(128), nullable=True)
    peak_equity: str = Column(Numeric(precision=20, scale=8), nullable=False, default="0")
    updated_at: datetime = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Account(Base):
    __tablename__ = "accounts"

    id: int = Column(Integer, primary_key=True)
    login: int = Column(Integer, nullable=False, unique=True)
    server: str = Column(String(128), nullable=False)
    name: str = Column(String(256))
    currency: str = Column(String(10))
    trade_mode: int = Column(Integer)
    leverage: int = Column(Integer)
    margin_mode: int = Column(Integer)
    first_seen: datetime = Column(DateTime(timezone=True), default=utcnow)
    last_seen: datetime = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Strategy(Base):
    __tablename__ = "strategies"

    id: int = Column(Integer, primary_key=True)
    strategy_id: str = Column(String(64), nullable=False, unique=True)
    name: str = Column(String(128))
    config_json: str = Column(Text)
    enabled: bool = Column(Boolean, default=False)
    created_at: datetime = Column(DateTime(timezone=True), default=utcnow)
    updated_at: datetime = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ConfigVersion(Base):
    __tablename__ = "config_versions"

    id: int = Column(Integer, primary_key=True)
    strategy_id: str = Column(String(64), nullable=False)
    config_hash: str = Column(String(64), nullable=False)
    config_json: str = Column(Text)
    author: str = Column(String(128), default="user")
    created_at: datetime = Column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_config_versions_strategy", "strategy_id", "created_at"),)


class StrategyRun(Base):
    __tablename__ = "strategy_runs"

    id: int = Column(Integer, primary_key=True)
    strategy_id: str = Column(String(64), nullable=False)
    config_hash: str = Column(String(64))
    mode: str = Column(String(32))    # DRY_RUN | DEMO_EXECUTION
    started_at: datetime = Column(DateTime(timezone=True), default=utcnow)
    stopped_at: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)
    stop_reason: str = Column(String(256), default="")


class Position(Base):
    __tablename__ = "positions"

    id: int = Column(Integer, primary_key=True)
    ticket: int = Column(Integer, nullable=False, unique=True)
    symbol: str = Column(String(32), nullable=False)
    direction: int = Column(Integer)    # 0=BUY, 1=SELL
    volume: str = Column(Numeric(precision=10, scale=4), nullable=False)
    price_open: str = Column(Numeric(precision=20, scale=8))
    sl: str = Column(Numeric(precision=20, scale=8), default=0)
    tp: str = Column(Numeric(precision=20, scale=8), default=0)
    magic: int = Column(Integer)
    comment: str = Column(String(64))
    basket_id: str = Column(String(64))
    basket_level: int = Column(Integer, default=0)
    scope: str = Column(String(16), default="BOT")   # BOT | MANUAL | FOREIGN | ORPHAN
    open_time: datetime = Column(DateTime(timezone=True))
    close_time: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)
    is_open: bool = Column(Boolean, default=True)
    mode: str = Column(String(32), default="DEMO_EXECUTION")  # or DRY_RUN

    __table_args__ = (
        UniqueConstraint("basket_id", "basket_level", name="uq_basket_level"),
        Index("ix_positions_ticket", "ticket"),
        Index("ix_positions_magic_open_time", "magic", "open_time"),
    )


class Order(Base):
    __tablename__ = "orders"

    id: int = Column(Integer, primary_key=True)
    correlation_id: str = Column(String(64), nullable=False, unique=True)
    strategy_id: str = Column(String(64))
    basket_id: str = Column(String(64))
    basket_level: int = Column(Integer)
    symbol: str = Column(String(32))
    order_type: int = Column(Integer)
    direction: int = Column(Integer)
    volume_requested: str = Column(Numeric(precision=10, scale=4))
    volume_filled: str = Column(Numeric(precision=10, scale=4), default=0)
    price_requested: str = Column(Numeric(precision=20, scale=8))
    price_filled: str = Column(Numeric(precision=20, scale=8), default=0)
    sl: str = Column(Numeric(precision=20, scale=8), default=0)
    tp: str = Column(Numeric(precision=20, scale=8), default=0)
    slippage_points: int = Column(Integer, default=0)
    magic: int = Column(Integer)
    comment: str = Column(String(64))
    retcode: int = Column(Integer)
    retcode_name: str = Column(String(64))
    success: bool = Column(Boolean)
    latency_ms: str = Column(Numeric(precision=10, scale=2), default=0)
    mt5_order_ticket: int = Column(Integer)
    mt5_deal_ticket: int = Column(Integer)
    mode: str = Column(String(32))
    risk_verdict_json: str = Column(Text)
    created_at: datetime = Column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        Index("ix_orders_basket", "basket_id", "created_at"),
        Index("ix_orders_magic", "magic", "created_at"),
    )


class Execution(Base):
    __tablename__ = "executions"

    id: int = Column(Integer, primary_key=True)
    order_id: int = Column(Integer, ForeignKey("orders.id"))
    position_ticket: int = Column(Integer)
    deal_ticket: int = Column(Integer)
    symbol: str = Column(String(32))
    direction: int = Column(Integer)
    volume: str = Column(Numeric(precision=10, scale=4))
    price: str = Column(Numeric(precision=20, scale=8))
    profit: str = Column(Numeric(precision=20, scale=8), default=0)
    commission: str = Column(Numeric(precision=20, scale=8), default=0)
    swap: str = Column(Numeric(precision=20, scale=8), default=0)
    executed_at: datetime = Column(DateTime(timezone=True), default=utcnow)


class PnlSnapshot(Base):
    __tablename__ = "pnl_snapshots"

    id: int = Column(Integer, primary_key=True)
    equity: str = Column(Numeric(precision=20, scale=8))
    balance: str = Column(Numeric(precision=20, scale=8))
    floating_pnl: str = Column(Numeric(precision=20, scale=8))
    realized_today: str = Column(Numeric(precision=20, scale=8))
    margin: str = Column(Numeric(precision=20, scale=8))
    free_margin: str = Column(Numeric(precision=20, scale=8))
    margin_level: str = Column(Numeric(precision=20, scale=8))
    open_positions: int = Column(Integer)
    captured_at: datetime = Column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_pnl_snapshots_time", "captured_at"),)


class RiskEvent(Base):
    __tablename__ = "risk_events"

    id: int = Column(Integer, primary_key=True)
    limit_name: str = Column(String(64))
    value: str = Column(String(128))
    limit: str = Column(String(128))
    action: str = Column(String(32))
    latching: bool = Column(Boolean, default=False)
    reason: str = Column(Text)
    resolved_at: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)
    created_at: datetime = Column(DateTime(timezone=True), default=utcnow)


class SystemEvent(Base):
    __tablename__ = "system_events"

    id: int = Column(Integer, primary_key=True)
    event_type: str = Column(String(64))   # state_change | reconciliation | alert | audit
    severity: str = Column(String(16))     # INFO | WARNING | ERROR | CRITICAL
    component: str = Column(String(64))
    message: str = Column(Text)
    payload_json: str = Column(Text, default="{}")
    correlation_id: str = Column(String(64))
    sequence_number: int = Column(Integer, default=0)
    created_at: datetime = Column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        Index("ix_system_events_type_time", "event_type", "created_at"),
        Index("ix_system_events_severity", "severity"),
    )


class ConnectionTest(Base):
    __tablename__ = "connection_tests"

    id: int = Column(Integer, primary_key=True)
    login: int = Column(Integer)
    server: str = Column(String(128))
    stages_json: str = Column(Text)        # per-stage pass/fail/latency
    overall_passed: bool = Column(Boolean, default=False)
    position_ticket: int = Column(Integer, nullable=True)
    cleanup_succeeded: bool = Column(Boolean, nullable=True)
    tested_at: datetime = Column(DateTime(timezone=True), default=utcnow)


class ErrorRow(Base):
    __tablename__ = "errors"

    id: int = Column(Integer, primary_key=True)
    component: str = Column(String(64))
    error_type: str = Column(String(128))
    message: str = Column(Text)
    mt5_code: int = Column(Integer, nullable=True)
    mt5_retcode: int = Column(Integer, nullable=True)
    correlation_id: str = Column(String(64))
    created_at: datetime = Column(DateTime(timezone=True), default=utcnow)


# ── Database Setup ────────────────────────────────────────────────────────────

_engine = None
_SessionLocal = None


def init_db(database_url: str) -> None:
    from sqlalchemy.orm import sessionmaker
    global _engine, _SessionLocal

    kwargs: dict = {}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        # Enable WAL for better concurrency on SQLite
        @event.listens_for(create_engine(database_url, **kwargs), "connect")
        def set_wal(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA journal_mode=WAL")

    _engine = create_engine(database_url, **kwargs)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)

    Base.metadata.create_all(_engine)
    log.info("database_initialized", url=database_url.split("@")[-1])  # no credentials


def get_session() -> Session:
    from sqlalchemy.orm import sessionmaker
    global _SessionLocal
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _SessionLocal()


def get_or_create_bot_state(session: Session) -> BotStateRow:
    row = session.get(BotStateRow, 1)
    if row is None:
        row = BotStateRow(id=1)
        session.add(row)
        session.commit()
    return row
