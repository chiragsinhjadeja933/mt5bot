"""
MT5 Account Data — Section 3 / 7
Reads account state from MT5 worker thread.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import structlog

log = structlog.get_logger(__name__)


@dataclass
class AccountState:
    login: int
    server: str
    name: str
    currency: str
    trade_mode: int          # 0=demo, 1=contest, 2=real
    leverage: int
    balance: Decimal
    equity: Decimal
    margin: Decimal
    free_margin: Decimal
    margin_level: Decimal    # equity/margin * 100; 0 if no margin
    profit: Decimal          # floating P/L
    margin_mode: int         # 0=netting, 2=hedging
    trade_allowed: bool
    trade_expert: bool
    margin_so_so: float      # stop-out level %
    margin_so_mode: int      # stop-out mode
    limit_orders: int        # max pending orders

    @property
    def is_demo(self) -> bool:
        return self.trade_mode == 0

    @property
    def is_hedging(self) -> bool:
        return self.margin_mode == 2

    @property
    def distance_to_stopout(self) -> Decimal | None:
        """Buffer between current margin level and stop-out level."""
        if self.margin_so_so <= 0 or self.margin_level <= 0:
            return None
        return self.margin_level - Decimal(str(self.margin_so_so))

    def to_dict(self) -> dict:
        return {
            "login": self.login,
            "server": self.server,
            "name": self.name,
            "currency": self.currency,
            "trade_mode": self.trade_mode,
            "trade_mode_name": {0: "DEMO", 1: "CONTEST", 2: "REAL"}.get(self.trade_mode, "UNKNOWN"),
            "leverage": self.leverage,
            "balance": str(self.balance),
            "equity": str(self.equity),
            "margin": str(self.margin),
            "free_margin": str(self.free_margin),
            "margin_level": str(self.margin_level),
            "profit": str(self.profit),
            "margin_mode": self.margin_mode,
            "margin_mode_name": {0: "NETTING", 2: "HEDGING"}.get(self.margin_mode, "UNKNOWN"),
            "trade_allowed": self.trade_allowed,
            "trade_expert": self.trade_expert,
            "stop_out_level": self.margin_so_so,
            "distance_to_stopout": str(self.distance_to_stopout) if self.distance_to_stopout else None,
        }


def read_account(mt5_module: object) -> AccountState:
    """Read account state. Must be called from the MT5 worker thread."""
    ai = mt5_module.account_info()  # type: ignore[attr-defined]
    if ai is None:
        from app.mt5.errors import Mt5Disconnected
        code, msg = mt5_module.last_error()  # type: ignore[attr-defined]
        raise Mt5Disconnected(f"account_info() returned None: [{code}] {msg}", code=code)

    margin = Decimal(str(ai.margin))
    equity = Decimal(str(ai.equity))
    margin_level = (equity / margin * Decimal("100")) if margin > 0 else Decimal("0")

    return AccountState(
        login=ai.login,
        server=ai.server,
        name=ai.name,
        currency=ai.currency,
        trade_mode=ai.trade_mode,
        leverage=ai.leverage,
        balance=Decimal(str(ai.balance)),
        equity=equity,
        margin=margin,
        free_margin=Decimal(str(ai.margin_free)),
        margin_level=margin_level,
        profit=Decimal(str(ai.profit)),
        margin_mode=ai.margin_mode,
        trade_allowed=ai.trade_allowed,
        trade_expert=ai.trade_expert,
        margin_so_so=ai.margin_so_so,
        margin_so_mode=ai.margin_so_mode,
        limit_orders=ai.limit_orders,
    )
