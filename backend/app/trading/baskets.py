"""
Basket Management — Section 11 [FIX/ADD]
A basket = group of positions with same magic + basket_id.
All P/L from MT5 position.profit + swap + entry commission.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

import structlog

log = structlog.get_logger(__name__)


class BasketState(str, Enum):
    ACTIVE = "ACTIVE"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"
    ERROR = "ERROR"


@dataclass
class BasketPosition:
    ticket: int
    direction: int          # 0=BUY, 1=SELL
    volume: Decimal
    price_open: Decimal
    profit: Decimal         # from MT5 position.profit
    swap: Decimal
    entry_commission: Decimal  # from entry deal
    comment: str
    level: int              # grid level (0-based)
    open_time: datetime


@dataclass
class Basket:
    basket_id: str
    strategy_id: str
    magic: int
    symbol: str
    direction: int          # 0=BUY, 1=SELL; -1=BOTH not valid here
    state: BasketState = BasketState.ACTIVE
    positions: list[BasketPosition] = field(default_factory=list)
    basket_tp: Decimal = Decimal("0")   # currency amount (positive = profit target)
    basket_sl: Decimal = Decimal("0")   # positive magnitude (e.g. 20 = lose 20)
    pnl_basis: str = "net"              # "net" or "gross"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── Computed properties ───────────────────────────────────────────────

    @property
    def total_volume(self) -> Decimal:
        return sum(p.volume for p in self.positions)

    @property
    def weighted_avg_entry(self) -> Decimal:
        """Σ(volume × price_open) / Σ(volume). Section 11 [ADD]."""
        total_vol = self.total_volume
        if total_vol == 0:
            return Decimal("0")
        return sum(p.volume * p.price_open for p in self.positions) / total_vol

    @property
    def floating_gross(self) -> Decimal:
        """Σ position.profit + Σ swap (from MT5 — account currency)."""
        return sum(p.profit + p.swap for p in self.positions)

    @property
    def entry_commissions(self) -> Decimal:
        return sum(p.entry_commission for p in self.positions)

    @property
    def floating_net(self) -> Decimal:
        """Gross + entry commission. Section 11 [ADD]."""
        return self.floating_gross + self.entry_commissions

    @property
    def current_pnl(self) -> Decimal:
        return self.floating_net if self.pnl_basis == "net" else self.floating_gross

    @property
    def position_count(self) -> int:
        return len(self.positions)

    def has_level(self, level: int) -> bool:
        return any(p.level == level for p in self.positions)

    def get_tickets(self) -> list[int]:
        return [p.ticket for p in self.positions]

    def should_take_profit(self) -> bool:
        if self.basket_tp <= 0 or self.state != BasketState.ACTIVE:
            return False
        return self.current_pnl >= self.basket_tp

    def should_stop_loss(self) -> bool:
        if self.basket_sl <= 0 or self.state != BasketState.ACTIVE:
            return False
        return self.current_pnl <= -self.basket_sl

    def to_dict(self) -> dict:
        return {
            "basket_id": self.basket_id,
            "strategy_id": self.strategy_id,
            "magic": self.magic,
            "symbol": self.symbol,
            "direction": self.direction,
            "direction_name": {0: "BUY", 1: "SELL"}.get(self.direction, "?"),
            "state": self.state,
            "position_count": self.position_count,
            "total_volume": str(self.total_volume),
            "weighted_avg_entry": str(self.weighted_avg_entry),
            "floating_gross": str(self.floating_gross),
            "floating_net": str(self.floating_net),
            "current_pnl": str(self.current_pnl),
            "basket_tp": str(self.basket_tp),
            "basket_sl": str(self.basket_sl),
            "pnl_basis": self.pnl_basis,
            "created_at": self.created_at.isoformat(),
            "positions": [
                {
                    "ticket": p.ticket,
                    "volume": str(p.volume),
                    "price_open": str(p.price_open),
                    "profit": str(p.profit),
                    "swap": str(p.swap),
                    "entry_commission": str(p.entry_commission),
                    "level": p.level,
                    "open_time": p.open_time.isoformat(),
                }
                for p in self.positions
            ],
        }


def parse_basket_id_from_comment(comment: str) -> tuple[str | None, int | None]:
    """
    Parse basket_id and level from comment.
    Format: "xg1|S|B7|L04|k9f2" or similar.
    Returns (basket_id, level) or (None, None) if not parseable.
    Section 17 [FIX]: parse defensively — brokers can modify comments.
    """
    try:
        parts = comment.split("|")
        # direction can be "B" or "S", so basket_part must be longer than 1 character
        basket_part = next((p for p in parts if p.startswith("B") and len(p) > 1), None)
        level_part = next((p for p in parts if p.startswith("L") and len(p) > 1 and p[1:].isdigit()), None)
        basket_id = basket_part[1:] if basket_part else None
        level = int(level_part[1:]) if level_part else None
        return basket_id, level
    except Exception:
        return None, None


def build_comment(strategy_short: str, direction: str,
                  basket_short: str, level: int, nonce: str) -> str:
    """
    Build a ≤31 char comment encoding basket identity.
    Section 17 [FIX].
    """
    comment = f"{strategy_short[:3]}|{direction[0]}|B{basket_short}|L{level:02d}|{nonce[:4]}"
    return comment[:31]
