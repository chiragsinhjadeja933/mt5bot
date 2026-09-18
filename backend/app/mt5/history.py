"""
MT5 Trade History — Sections 3, 8, 39
Reads deals and history orders. Commission lives on deals (not positions).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any

from app.mt5.timeutil import server_ts_to_utc

import structlog

log = structlog.get_logger(__name__)


@dataclass
class DealData:
    ticket: int
    position_id: int
    order: int
    symbol: str
    type: int          # 0=buy, 1=sell
    entry: int         # 0=entry, 1=exit, 2=reverse, 3=state
    volume: Decimal
    price: Decimal
    profit: Decimal
    commission: Decimal
    swap: Decimal
    fee: Decimal
    magic: int
    comment: str
    time: datetime
    reason: int        # DEAL_REASON constants

    @property
    def net_profit(self) -> Decimal:
        return self.profit + self.commission + self.swap + self.fee

    def to_dict(self) -> dict:
        return {
            "ticket": self.ticket,
            "position_id": self.position_id,
            "order": self.order,
            "symbol": self.symbol,
            "type": self.type,
            "entry": self.entry,
            "entry_name": {0: "IN", 1: "OUT", 2: "INOUT", 3: "STATE"}.get(self.entry, "?"),
            "volume": str(self.volume),
            "price": str(self.price),
            "profit": str(self.profit),
            "commission": str(self.commission),
            "swap": str(self.swap),
            "fee": str(self.fee),
            "net_profit": str(self.net_profit),
            "magic": self.magic,
            "comment": self.comment,
            "time": self.time.isoformat(),
            "reason": self.reason,
        }


def _parse_deal(d: Any) -> DealData:
    return DealData(
        ticket=d.ticket,
        position_id=d.position_id,
        order=d.order,
        symbol=d.symbol,
        type=d.type,
        entry=d.entry,
        volume=Decimal(str(d.volume)),
        price=Decimal(str(d.price)),
        profit=Decimal(str(d.profit)),
        commission=Decimal(str(d.commission)),
        swap=Decimal(str(d.swap)),
        fee=Decimal(str(getattr(d, "fee", 0))),
        magic=d.magic,
        comment=d.comment or "",
        time=server_ts_to_utc(d.time * 1000),
        reason=d.reason,
    )


def get_deals_by_position(position_id: int, mt5_module: Any,
                           retry_seconds: float = 5.0) -> list[DealData]:
    """
    Get entry+exit deals for a position ID.
    Retries for retry_seconds because deal history can lag MT5.
    Section 5 [ADD].
    """
    import time
    deadline = time.monotonic() + retry_seconds
    while True:
        deals = mt5_module.history_deals_get(position=position_id)
        if deals and len(deals) >= 1:
            return [_parse_deal(d) for d in deals]
        if time.monotonic() >= deadline:
            return []
        time.sleep(0.5)


def get_deals_range(from_dt: datetime, to_dt: datetime,
                    mt5_module: Any) -> list[DealData]:
    """Get all deals in a datetime range."""
    raw = mt5_module.history_deals_get(from_dt, to_dt)
    if raw is None:
        return []
    return [_parse_deal(d) for d in raw]


def get_deals_today(mt5_module: Any) -> list[DealData]:
    """Get today's deals (UTC midnight to now)."""
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return get_deals_range(start, now, mt5_module)
