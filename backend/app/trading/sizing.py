"""
Position Sizing Engine — Section 12 [ADD]
Pure functions using Decimal — no float equality, no rounding up past budget.
Fully unit-testable without MT5.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import NamedTuple

import structlog

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class BrokerVolumeSpec:
    """Broker volume constraints — always read from MT5, never hardcoded."""
    volume_min: Decimal
    volume_max: Decimal
    volume_step: Decimal
    volume_limit: Decimal  # 0 = no limit


@dataclass(frozen=True)
class TickSpec:
    """Tick value data for P/L computation."""
    tick_size: float
    tick_value: float       # per lot per tick (gain side)
    tick_value_loss: float  # per lot per tick (loss side)
    trade_contract_size: float
    point: float


class SizingResult(NamedTuple):
    requested_lots: Decimal  # before rounding
    effective_lots: Decimal  # after rounding to step, clamping
    reason_rejected: str     # non-empty if no trade should be placed


def round_volume(volume: Decimal, spec: BrokerVolumeSpec) -> Decimal:
    """
    Round DOWN to volume_step using Decimal (avoids float artifacts).
    0.30000000000000004 → 0.30 etc.
    """
    step = spec.volume_step
    if step <= 0:
        return volume
    # Quantize down
    rounded = (volume / step).to_integral_value(rounding=ROUND_DOWN) * step
    # Clamp
    rounded = max(spec.volume_min, min(spec.volume_max, rounded))
    return rounded.normalize()


def compute_risk_lots(
    risk_pct: Decimal,
    account_equity: Decimal,
    stop_distance_points: int,
    tick_spec: TickSpec,
    broker_spec: BrokerVolumeSpec,
) -> SizingResult:
    """
    Risk-based lot calculation. Section 12 [ADD].
    risk_amount = equity × risk_pct / 100
    lots = risk_amount / ((stop_distance / point * tick_size) / tick_size × tick_value_loss × 1)
         = risk_amount / (stop_distance_points × tick_value_loss)
    tick_value_loss already accounts for account currency conversion.
    """
    if account_equity <= 0:
        return SizingResult(Decimal("0"), Decimal("0"), "equity_zero")
    if stop_distance_points <= 0:
        return SizingResult(Decimal("0"), Decimal("0"), "stop_distance_zero")

    risk_amount = account_equity * risk_pct / Decimal("100")
    tick_val_loss = Decimal(str(tick_spec.tick_value_loss))

    if tick_val_loss <= 0:
        return SizingResult(Decimal("0"), Decimal("0"), "tick_value_loss_zero")

    raw_lots = risk_amount / (Decimal(str(stop_distance_points)) * tick_val_loss)

    if raw_lots < broker_spec.volume_min:
        # Don't round up beyond risk budget unless config allows
        return SizingResult(
            raw_lots, Decimal("0"),
            f"risk_lots_below_volume_min: {raw_lots} < {broker_spec.volume_min}"
        )

    effective = round_volume(raw_lots, broker_spec)
    return SizingResult(raw_lots, effective, "")


def validate_volume(
    volume: Decimal,
    spec: BrokerVolumeSpec,
    current_total: Decimal | None = None,
    max_total_lots: Decimal | None = None,
) -> str:
    """Returns error string if invalid, empty string if OK."""
    if volume < spec.volume_min:
        return f"volume {volume} < volume_min {spec.volume_min}"
    if volume > spec.volume_max:
        return f"volume {volume} > volume_max {spec.volume_max}"

    # Check step alignment
    if spec.volume_step > 0:
        remainder = (volume % spec.volume_step).normalize()
        if remainder != Decimal("0"):
            return f"volume {volume} not aligned to step {spec.volume_step}"

    # Total volume check
    if current_total is not None and max_total_lots is not None and max_total_lots > 0:
        if current_total + volume > max_total_lots:
            return (f"total lots {current_total + volume} "
                    f"> max_total_lots {max_total_lots}")

    if spec.volume_limit > 0:
        total = (current_total or Decimal("0")) + volume
        if total > spec.volume_limit:
            return f"volume_limit {spec.volume_limit} would be exceeded"

    return ""


def grid_lots_at_level(
    level: int,           # 0-based
    initial_lot: Decimal,
    lot_mode: str,        # "fixed" | "multiplier" | "custom"
    lot_multiplier: float = 1.0,
    custom_lots: list[Decimal] | None = None,
    max_lot: Decimal = Decimal("1.0"),
    broker_spec: BrokerVolumeSpec | None = None,
) -> Decimal:
    """
    Compute the lot size for a given grid level.
    Volumes are rounded DOWN to broker step and clamped to max_lot.
    Section 10 [FIX].
    """
    if lot_mode == "fixed":
        raw = initial_lot
    elif lot_mode == "multiplier":
        raw = initial_lot * Decimal(str(lot_multiplier)) ** level
    elif lot_mode == "custom" and custom_lots:
        idx = min(level, len(custom_lots) - 1)
        raw = custom_lots[idx]
    else:
        raw = initial_lot

    # Cap at max_lot
    raw = min(raw, max_lot)

    # Round to step if spec provided
    if broker_spec:
        raw = round_volume(raw, broker_spec)

    return raw


def worst_case_lots(
    max_positions: int,
    initial_lot: Decimal,
    lot_mode: str,
    lot_multiplier: float,
    max_lot: Decimal,
    broker_spec: BrokerVolumeSpec,
) -> list[Decimal]:
    """Return effective lot at each level (used for exposure preview)."""
    return [
        grid_lots_at_level(i, initial_lot, lot_mode, lot_multiplier,
                            max_lot=max_lot, broker_spec=broker_spec)
        for i in range(max_positions)
    ]


def calc_floating_pnl(
    price_open: Decimal,
    price_current: Decimal,
    volume: Decimal,
    direction: int,         # 0=BUY, 1=SELL
    tick_spec: TickSpec,
) -> Decimal:
    """
    THEORETICAL P/L calculation for exposure preview / dry-run.
    Section 39 [ADD]: use tick-value formula, never raw delta.
    BUY profit when price rises; SELL profit when price falls.
    """
    if direction == 0:  # BUY
        delta = price_current - price_open
    else:               # SELL
        delta = price_open - price_current

    point = Decimal(str(tick_spec.point))
    tick_size = Decimal(str(tick_spec.tick_size))
    if tick_size <= 0 or point <= 0:
        return Decimal("0")

    ticks = delta / tick_size
    if delta >= 0:
        tv = Decimal(str(tick_spec.tick_value))
    else:
        tv = Decimal(str(tick_spec.tick_value_loss))

    return ticks * tv * volume
