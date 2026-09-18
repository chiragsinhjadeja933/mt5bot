"""
MT5 Positions Reader — Section 3
Reads open positions from MT5 worker thread.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from typing import Any

from app.mt5.timeutil import server_ts_to_utc

import structlog

log = structlog.get_logger(__name__)


@dataclass
class PositionData:
    ticket: int
    symbol: str
    type: int           # 0=BUY, 1=SELL
    volume: Decimal
    price_open: Decimal
    price_current: Decimal
    sl: Decimal
    tp: Decimal
    profit: Decimal     # floating (does not include commission)
    swap: Decimal
    magic: int
    comment: str
    open_time: datetime
    identifier: int     # position id

    @property
    def direction(self) -> str:
        return "BUY" if self.type == 0 else "SELL"

    def to_dict(self) -> dict:
        return {
            "ticket": self.ticket,
            "symbol": self.symbol,
            "type": self.type,
            "direction": self.direction,
            "volume": str(self.volume),
            "price_open": str(self.price_open),
            "price_current": str(self.price_current),
            "sl": str(self.sl),
            "tp": str(self.tp),
            "profit": str(self.profit),
            "swap": str(self.swap),
            "magic": self.magic,
            "comment": self.comment,
            "open_time": self.open_time.isoformat(),
            "identifier": self.identifier,
        }


def read_positions(mt5_module: Any, symbol: str | None = None,
                   magic: int | None = None) -> list[PositionData]:
    """Read open positions. Filter by symbol and/or magic if given."""
    if symbol:
        raw = mt5_module.positions_get(symbol=symbol)
    elif magic:
        raw = mt5_module.positions_get(magic=magic)
    else:
        raw = mt5_module.positions_get()

    if raw is None:
        return []

    result = []
    for p in raw:
        if magic is not None and p.magic != magic:
            continue
        result.append(PositionData(
            ticket=p.ticket,
            symbol=p.symbol,
            type=p.type,
            volume=Decimal(str(p.volume)),
            price_open=Decimal(str(p.price_open)),
            price_current=Decimal(str(p.price_current)),
            sl=Decimal(str(p.sl)),
            tp=Decimal(str(p.tp)),
            profit=Decimal(str(p.profit)),
            swap=Decimal(str(p.swap)),
            magic=p.magic,
            comment=p.comment or "",
            open_time=server_ts_to_utc(p.time * 1000),
            identifier=p.identifier,
        ))
    return result
