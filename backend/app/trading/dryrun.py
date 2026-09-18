"""
DryRun Gateway — Section 31 [ADD]
Same interface as Mt5Gateway.
Uses real market data; fills are THEORETICAL.
Virtual positions stored separately; never mixed with MT5 data.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import structlog

from app.mt5.gateway import TradingGateway, OrderRequest, OrderResult
from app.mt5.retcodes import RetcodeInfo

log = structlog.get_logger(__name__)
THEORETICAL_PROVENANCE = "THEORETICAL — DRY RUN"


@dataclass
class VirtualPosition:
    ticket: int
    symbol: str
    type: int
    volume: Decimal
    price_open: Decimal
    sl: float
    tp: float
    magic: int
    comment: str
    open_time: datetime
    basket_id: str = ""

    def direction(self) -> str:
        return "BUY" if self.type == 0 else "SELL"

    def to_dict(self) -> dict:
        return {
            "ticket": self.ticket,
            "symbol": self.symbol,
            "type": self.type,
            "direction": self.direction(),
            "volume": str(self.volume),
            "price_open": str(self.price_open),
            "sl": self.sl,
            "tp": self.tp,
            "magic": self.magic,
            "comment": self.comment,
            "open_time": self.open_time.isoformat(),
            "provenance": THEORETICAL_PROVENANCE,
        }


class DryRunGateway(TradingGateway):
    """
    DryRunGateway — same seam as Mt5Gateway.
    Virtual fills using real bid/ask.
    THEORETICAL labels on everything.
    Risk limits, cooldowns, staleness still honored.
    """

    def __init__(self, real_gateway: TradingGateway) -> None:
        self._real = real_gateway  # used for account, tick, deals
        self._lock = threading.Lock()
        self._positions: dict[int, VirtualPosition] = {}
        self._next_ticket = 9_000_001

    def get_account(self) -> Any:
        return self._real.get_account()

    def get_tick(self, symbol: str) -> Any:
        return self._real.get_tick(symbol)

    def get_positions(self, symbol: str | None = None, magic: int | None = None) -> list:
        with self._lock:
            positions = list(self._positions.values())
        if symbol:
            positions = [p for p in positions if p.symbol == symbol]
        if magic:
            positions = [p for p in positions if p.magic == magic]
        return positions

    def send_order(self, request: OrderRequest) -> OrderResult:
        """Virtual fill using real bid/ask (BUY at ask, SELL at bid). Section 31 [ADD]."""
        tick = self._real.get_tick(request.symbol)
        if request.order_type == 0:  # BUY
            fill_price = float(tick.ask)
        else:  # SELL
            fill_price = float(tick.bid)

        with self._lock:
            ticket = self._next_ticket
            self._next_ticket += 1
            vpos = VirtualPosition(
                ticket=ticket,
                symbol=request.symbol,
                type=request.order_type,
                volume=request.volume,
                price_open=Decimal(str(fill_price)),
                sl=request.sl,
                tp=request.tp,
                magic=request.magic,
                comment=f"[DRY]{request.comment}"[:31],
                open_time=datetime.now(timezone.utc),
            )
            self._positions[ticket] = vpos

        log.info("dryrun_virtual_fill",
                 ticket=ticket, symbol=request.symbol,
                 volume=str(request.volume), fill_price=fill_price,
                 direction={0: "BUY", 1: "SELL"}.get(request.order_type),
                 note="THEORETICAL — NOT SENT TO MT5")

        return OrderResult(
            request=request,
            retcode=10009,  # DONE
            retcode_name="DONE",
            order_ticket=ticket,
            deal_ticket=ticket,
            volume_filled=request.volume,
            price_filled=fill_price,
            comment="DRY_RUN_VIRTUAL_FILL",
            request_id=0,
            success=True,
            latency_ms=0.0,
            slippage_points=0,
            raw_result={"dry_run": True, "provenance": THEORETICAL_PROVENANCE},
        )

    def close_position(self, ticket: int, symbol: str, volume: Decimal,
                       order_type: int, price: float, deviation: int,
                       magic: int, comment: str) -> OrderResult:
        with self._lock:
            pos = self._positions.pop(ticket, None)

        req = OrderRequest(symbol=symbol, order_type=order_type,
                           volume=volume, price=price, magic=magic,
                           comment=comment)
        if pos is None:
            return OrderResult(req, 10036, "POSITION_CLOSED", ticket, 0,
                               volume, price, "already_closed", 0, True, 0.0, 0, {})

        log.info("dryrun_virtual_close", ticket=ticket, provenance=THEORETICAL_PROVENANCE)
        return OrderResult(req, 10009, "DONE", ticket, ticket,
                           volume, price, "DRY_RUN_CLOSE", 0, True, 0.0, 0,
                           {"dry_run": True})

    def modify_position(self, ticket: int, sl: float, tp: float) -> bool:
        with self._lock:
            pos = self._positions.get(ticket)
            if pos:
                pos.sl = sl
                pos.tp = tp
        return pos is not None

    def get_deals(self, position_id: int) -> list:
        return []  # No real deals in dry run

    def order_calc_margin(self, order_type: int, symbol: str,
                          volume: Decimal, price: float) -> float | None:
        return self._real.order_calc_margin(order_type, symbol, volume, price)

    def order_check(self, request: OrderRequest) -> tuple[int, str]:
        return 0, "DRY_RUN_OK"

    @property
    def virtual_positions(self) -> list[VirtualPosition]:
        with self._lock:
            return list(self._positions.values())
