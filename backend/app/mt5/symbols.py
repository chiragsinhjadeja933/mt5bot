"""
MT5 Symbol Resolution & Broker Constraints — Section 18 [ADD] / symbols.py
Reads all specs from MT5 — nothing hardcoded.
"""
from __future__ import annotations

import structlog
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass  # MT5 imported inside functions to stay importable on non-Windows

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SymbolSpec:
    """All broker-provided constraints for a symbol. Nothing hardcoded."""
    name: str
    digits: int
    point: float               # 1 point in price units
    tick_size: float
    tick_value: float          # account currency per tick per lot (for gain)
    tick_value_loss: float     # account currency per tick per lot (for loss side)
    trade_contract_size: float # e.g. 100 oz for XAUUSD
    volume_min: Decimal
    volume_max: Decimal
    volume_step: Decimal
    volume_limit: Decimal      # max total volume; 0 = no limit
    trade_stops_level: int     # minimum SL/TP distance in points
    trade_freeze_level: int    # cannot modify within this distance
    filling_mode: int          # bitmask: 1=FOK, 2=IOC, 4=RETURN
    trade_mode: int            # 0=disabled,1=long-only,2=short-only,4=full
    spread: int                # current spread in points
    currency_base: str
    currency_profit: str
    currency_margin: str

    def point_to_price(self, points: int) -> float:
        return points * self.point

    def price_to_points(self, price_diff: float) -> int:
        return round(price_diff / self.point)

    def best_filling_mode(self) -> int:
        """Return the best supported filling mode constant."""
        # ORDER_FILLING_FOK=0, ORDER_FILLING_IOC=1, ORDER_FILLING_RETURN=2
        if self.filling_mode & 1:
            return 0  # FOK
        if self.filling_mode & 2:
            return 1  # IOC
        if self.filling_mode & 4:
            return 2  # RETURN
        return 0  # fallback, will be caught by order_check

    def is_tradeable(self) -> bool:
        return self.trade_mode == 4  # SYMBOL_TRADE_MODE_FULL


def resolve_symbol(target: str, mt5_module: object) -> str | None:
    """
    Try to find the broker's actual gold symbol.
    Returns the exact symbol name or None.
    Never auto-trades a guessed symbol — caller must confirm.
    """
    import MetaTrader5 as mt5_  # only available on Windows
    mt5_ = mt5_module  # type: ignore[assignment]

    candidates = [target]
    # Try common aliases if exact match not found
    if not any(c == target for c in candidates):
        candidates = [target]

    # Try exact name first
    info = mt5_.symbol_info(target)
    if info is not None:
        return target

    # Search with wildcard
    all_symbols = mt5_.symbols_get(f"{target[:3]}*") or []
    log.info("symbol_search_candidates",
             query=target,
             found=[s.name for s in all_symbols[:10]])

    for sym in all_symbols:
        if sym.name.upper().startswith("XAU") or sym.name.upper().startswith("GOLD"):
            log.warning("symbol_alias_found_needs_confirmation",
                        configured=target, found=sym.name)
            return sym.name  # Caller must present this to user for confirmation

    return None


def read_symbol_spec(symbol: str, mt5_module: object) -> SymbolSpec:
    """Read all broker constraints for symbol. Raises Mt5SymbolNotFound if unavailable."""
    from app.mt5.errors import Mt5SymbolNotFound

    info = mt5_module.symbol_info(symbol)  # type: ignore[attr-defined]
    if info is None:
        raise Mt5SymbolNotFound(
            f"Symbol '{symbol}' not found in MT5. "
            "Ensure it is in Market Watch (symbol_select first).",
            code=-4,
        )

    tv = getattr(info, "trade_tick_value", None) or info.trade_tick_value
    tv_loss = getattr(info, "trade_tick_value_loss", None) or tv

    return SymbolSpec(
        name=info.name,
        digits=info.digits,
        point=info.point,
        tick_size=info.trade_tick_size,
        tick_value=tv,
        tick_value_loss=tv_loss,
        trade_contract_size=info.trade_contract_size,
        volume_min=Decimal(str(info.volume_min)),
        volume_max=Decimal(str(info.volume_max)),
        volume_step=Decimal(str(info.volume_step)),
        volume_limit=Decimal(str(info.volume_limit)) if info.volume_limit > 0 else Decimal("0"),
        trade_stops_level=info.trade_stops_level,
        trade_freeze_level=info.trade_freeze_level,
        filling_mode=info.filling_mode,
        trade_mode=info.trade_mode,
        spread=info.spread,
        currency_base=info.currency_base,
        currency_profit=info.currency_profit,
        currency_margin=info.currency_margin,
    )
