"""
MT5 Market Data — Section 18
Tick polling (100–250 ms on worker thread), candles, session info.
Staleness / frozen-feed detection.
Sanity checks on every tick.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, timezone
from typing import Any

import structlog

from app.mt5.timeutil import server_ts_to_utc

log = structlog.get_logger(__name__)

# Typical XAUUSD contract has last=0 from some brokers — use mid instead
_MAX_PLAUSIBLE_SPREAD_POINTS = 1000  # sanity guard
_MAX_SINGLE_TICK_JUMP_POINTS = 5000


@dataclass
class TickData:
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal      # may be 0 for some CFDs — use mid if 0
    spread_points: int
    server_time: datetime  # in real UTC
    time_msc: int          # raw mt5 millisecond timestamp
    age_ms: float = 0.0   # populated by market data service
    is_stale: bool = False
    is_frozen: bool = False
    provenance: str = "MT5"

    @property
    def mid(self) -> Decimal:
        return (self.bid + self.ask) / 2

    @property
    def display_price(self) -> Decimal:
        """Show mid if last is 0 (common for gold CFDs). Section 7 [ADD]."""
        return self.last if self.last > 0 else self.mid

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "bid": str(self.bid),
            "ask": str(self.ask),
            "mid": str(self.mid),
            "last": str(self.last),
            "display_price": str(self.display_price),
            "spread_points": self.spread_points,
            "server_time": self.server_time.isoformat(),
            "age_ms": round(self.age_ms, 1),
            "is_stale": self.is_stale,
            "is_frozen": self.is_frozen,
            "provenance": self.provenance,
        }


@dataclass
class CandleData:
    symbol: str
    timeframe: int
    time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    tick_volume: int
    real_volume: int
    spread: int


def read_tick(symbol: str, mt5_module: Any,
              max_spread_points: int = 200,
              prev_bid: Decimal | None = None,
              max_jump_points: int = _MAX_SINGLE_TICK_JUMP_POINTS) -> TickData:
    """
    Read and sanity-check a tick. Must run on MT5 worker thread.
    Raises on invalid data.
    """
    tick = mt5_module.symbol_info_tick(symbol)
    if tick is None:
        from app.mt5.errors import Mt5SymbolNotFound
        code, msg = mt5_module.last_error()
        raise Mt5SymbolNotFound(
            f"symbol_info_tick('{symbol}') failed: [{code}] {msg}",
            code=code,
        )

    bid = Decimal(str(tick.bid))
    ask = Decimal(str(tick.ask))
    last = Decimal(str(tick.last))

    # Sanity checks
    if bid <= 0 or ask <= 0:
        log.warning("tick_sanity_failed_zero_price", symbol=symbol, bid=float(bid), ask=float(ask))
        raise ValueError(f"Invalid tick: bid={bid} ask={ask}")

    if ask < bid:
        log.warning("tick_sanity_failed_ask_lt_bid", symbol=symbol, bid=float(bid), ask=float(ask))
        raise ValueError(f"Invalid tick: ask({ask}) < bid({bid})")

    # Get symbol info for point size
    sym_info = mt5_module.symbol_info(symbol)
    point = sym_info.point if sym_info else 0.01
    spread_points = round(float(ask - bid) / point)

    if spread_points > _MAX_PLAUSIBLE_SPREAD_POINTS:
        log.warning("tick_sanity_spread_spike",
                    symbol=symbol, spread_points=spread_points,
                    max=_MAX_PLAUSIBLE_SPREAD_POINTS)

    # Jump detection
    if prev_bid is not None:
        jump = abs(bid - prev_bid)
        jump_points = round(float(jump) / point)
        if jump_points > max_jump_points:
            log.warning("tick_sanity_price_jump",
                        symbol=symbol, jump_points=jump_points,
                        prev=float(prev_bid), new=float(bid))

    server_time = server_ts_to_utc(tick.time_msc if tick.time_msc else tick.time * 1000)
    age_ms = (time.time() - tick.time) * 1000

    return TickData(
        symbol=symbol,
        bid=bid,
        ask=ask,
        last=last,
        spread_points=spread_points,
        server_time=server_time,
        time_msc=tick.time_msc if tick.time_msc else tick.time * 1000,
        age_ms=age_ms,
    )


def read_candles(symbol: str, timeframe: int, count: int,
                 mt5_module: Any) -> list[CandleData]:
    """Read N most recent bars. timeframe uses MT5 TIMEFRAME_* constants."""
    rates = mt5_module.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None or len(rates) == 0:
        return []

    result = []
    for r in rates:
        result.append(CandleData(
            symbol=symbol,
            timeframe=timeframe,
            time=server_ts_to_utc(r["time"] * 1000),
            open=Decimal(str(r["open"])),
            high=Decimal(str(r["high"])),
            low=Decimal(str(r["low"])),
            close=Decimal(str(r["close"])),
            tick_volume=int(r["tick_volume"]),
            real_volume=int(r.get("real_volume", 0)),
            spread=int(r.get("spread", 0)),
        ))
    return result
