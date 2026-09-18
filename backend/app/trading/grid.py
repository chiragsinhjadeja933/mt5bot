"""
Grid Strategy Engine — Section 10 [FIX/ADD]
Pure/deterministic — no MT5 imports, no datetime.now() (injected Clock).
Emits OrderIntents only; never calls MT5.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Protocol, runtime_checkable

import structlog

from app.trading.sizing import grid_lots_at_level, BrokerVolumeSpec

log = structlog.get_logger(__name__)


# ── Clock Protocol (injected for testability) ────────────────────────────────
@runtime_checkable
class Clock(Protocol):
    def now_monotonic(self) -> float: ...
    def now_utc_timestamp(self) -> float: ...


class SystemClock:
    import time as _time
    def now_monotonic(self) -> float:
        import time
        return time.monotonic()
    def now_utc_timestamp(self) -> float:
        import time
        return time.time()


# ── Market / Portfolio Snapshots ─────────────────────────────────────────────
@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    bid: Decimal
    ask: Decimal
    spread_points: int
    timestamp_monotonic: float
    is_stale: bool = False
    is_market_open: bool = True


@dataclass(frozen=True)
class PortfolioSnapshot:
    equity: Decimal
    balance: Decimal
    free_margin: Decimal
    margin_level: Decimal
    open_positions: int
    total_volume: Decimal
    basket_pnl: Decimal = Decimal("0")
    last_entry_price: Decimal | None = None
    avg_entry_price: Decimal | None = None
    basket_position_count: int = 0


# ── Order Intent ─────────────────────────────────────────────────────────────
class IntentClass(str, Enum):
    ENTRY = "ENTRY"
    REDUCE = "REDUCE"
    EMERGENCY_CLOSE = "EMERGENCY_CLOSE"


@dataclass
class OrderIntent:
    symbol: str
    direction: int          # 0=BUY, 1=SELL
    volume: Decimal
    intent_class: IntentClass
    strategy_id: str
    basket_id: str
    level: int
    magic: int
    comment: str
    reason: str
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    config_hash: str = ""
    sl_points: int = 0       # protective SL in points from entry
    tp_points: int = 0


# ── Grid Config ───────────────────────────────────────────────────────────────
@dataclass
class GridConfig:
    strategy_id: str
    symbol: str
    direction: int             # 0=BUY, 1=SELL
    grid_mode: str             # "adverse" | "favorable"
    grid_anchor: str           # "last_entry" | "average_entry"
    first_entry: str           # "manual_trigger" | "immediate_on_start" | "signal"
    initial_lot: Decimal
    lot_mode: str              # "fixed" | "multiplier" | "custom"
    lot_multiplier: float = 1.0
    allow_multiplier: bool = False
    custom_lots: list[Decimal] = field(default_factory=list)
    max_lot: Decimal = Decimal("0.05")
    max_total_lots: Decimal = Decimal("0.20")
    max_positions: int = 20
    grid_distance_points: int = 100
    basket_take_profit: Decimal = Decimal("10.0")
    basket_stop_loss: Decimal = Decimal("20.0")
    pnl_basis: str = "net"
    protective_sl_points: int = 5000
    max_slippage_points: int = 30
    max_spread_points: int = 60
    cooldown_seconds: float = 60.0
    rearm_after_basket_close: bool = False
    rearm_delay_seconds: float = 300.0
    max_entries_per_hour: int = 20
    allowed_sessions: list[tuple[str, str]] = field(default_factory=list)
    aggressive_mode: bool = False
    magic: int = 10001
    config_hash: str = ""
    schema_version: int = 1

    def __post_init__(self) -> None:
        # Validate martingale flag
        if self.lot_multiplier > 1.0 and not self.allow_multiplier:
            raise ValueError(
                f"lot_multiplier={self.lot_multiplier} > 1.0 requires allow_multiplier=true. "
                "This is a MARTINGALE/AVERAGING strategy — HIGH RISK."
            )

    @property
    def basket_direction_name(self) -> str:
        return {0: "BUY", 1: "SELL"}.get(self.direction, "?")


# ── Strategy State ────────────────────────────────────────────────────────────
@dataclass
class GridStrategyState:
    config: GridConfig
    basket_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    last_entry_price: Decimal | None = None
    last_entry_time_monotonic: float = 0.0
    position_count: int = 0
    waiting_for_first_entry: bool = True
    armed: bool = True

    def reset_for_new_basket(self) -> None:
        self.basket_id = str(uuid.uuid4())[:8]
        self.last_entry_price = None
        self.last_entry_time_monotonic = 0.0
        self.position_count = 0
        self.waiting_for_first_entry = True
        self.armed = True

    def to_dict(self) -> dict:
        return {
            "basket_id": self.basket_id,
            "last_entry_price": str(self.last_entry_price) if self.last_entry_price else None,
            "position_count": self.position_count,
            "waiting_for_first_entry": self.waiting_for_first_entry,
            "armed": self.armed,
        }


# ── Strategy Protocol ─────────────────────────────────────────────────────────
@runtime_checkable
class Strategy(Protocol):
    def on_market(self, snapshot: MarketSnapshot, portfolio: PortfolioSnapshot,
                  clock: Clock) -> list[OrderIntent]: ...
    def on_fill(self, fill: "Fill") -> None: ...
    def state(self) -> dict: ...


@dataclass
class Fill:
    basket_id: str
    level: int
    direction: int
    volume: Decimal
    price_filled: Decimal
    ticket: int
    monotonic_time: float


# ── Grid Strategy Implementation ──────────────────────────────────────────────
class XAUUSDGridStrategy:
    """
    Configurable XAUUSD grid/basket strategy.
    Pure/deterministic — no MT5 imports, no side effects.
    Emits OrderIntent objects; execution pipeline handles sending.
    Section 10 [FIX].
    """

    def __init__(self, config: GridConfig,
                 broker_spec: BrokerVolumeSpec | None = None) -> None:
        self._cfg = config
        self._broker_spec = broker_spec
        self._state = GridStrategyState(config=config)

    def on_market(
        self,
        snapshot: MarketSnapshot,
        portfolio: PortfolioSnapshot,
        clock: Clock,
    ) -> list[OrderIntent]:
        """
        Called on every tick (via engine loop, sequentially — no races).
        Returns list of OrderIntents (usually 0 or 1).
        """
        intents: list[OrderIntent] = []
        cfg = self._cfg
        state = self._state

        # ── Pre-conditions ────────────────────────────────────────────────
        if not state.armed:
            return []
        if snapshot.is_stale or not snapshot.is_market_open:
            return []
        if snapshot.spread_points > cfg.max_spread_points:
            log.debug("strategy_skip_spread_too_wide",
                      spread=snapshot.spread_points, max=cfg.max_spread_points)
            return []
        if state.position_count >= cfg.max_positions:
            return []

        # ── First entry ───────────────────────────────────────────────────
        if state.waiting_for_first_entry:
            if cfg.first_entry == "immediate_on_start":
                intent = self._build_intent(snapshot, state, portfolio, 0)
                if intent:
                    intents.append(intent)
            # "manual_trigger" and "signal" handled externally
            return intents

        # ── Cooldown check ────────────────────────────────────────────────
        now = clock.now_monotonic()
        elapsed = now - state.last_entry_time_monotonic
        if elapsed < cfg.cooldown_seconds:
            log.debug("strategy_skip_cooldown",
                      remaining=round(cfg.cooldown_seconds - elapsed, 1))
            return []

        # ── Grid trigger ──────────────────────────────────────────────────
        if state.last_entry_price is None:
            return []

        # Reference price based on anchor config
        if cfg.grid_anchor == "average_entry":
            ref_price = portfolio.avg_entry_price or state.last_entry_price
        else:
            ref_price = state.last_entry_price

        # BUY=ask reference, SELL=bid reference (Section 10 [FIX])
        current_ref = snapshot.ask if cfg.direction == 0 else snapshot.bid

        price_move = current_ref - ref_price  # positive = price went up

        # For SELL + "adverse": add when price rises (against the basket)
        # For BUY + "adverse":  add when price falls (against the basket)
        if cfg.direction == 1:  # SELL basket
            if cfg.grid_mode == "adverse":
                triggered = price_move >= self._distance_in_price(cfg, snapshot)
            else:  # favorable
                triggered = price_move <= -self._distance_in_price(cfg, snapshot)
        else:  # BUY basket
            if cfg.grid_mode == "adverse":
                triggered = price_move <= -self._distance_in_price(cfg, snapshot)
            else:
                triggered = price_move >= self._distance_in_price(cfg, snapshot)

        if triggered:
            level = state.position_count
            intent = self._build_intent(snapshot, state, portfolio, level)
            if intent:
                intents.append(intent)

        return intents

    def _distance_in_price(self, cfg: GridConfig, snap: MarketSnapshot) -> Decimal:
        """Convert grid_distance_points to price units."""
        # Need broker point — use spread as proxy if no spec
        if self._broker_spec:
            point = Decimal(str(self._broker_spec.volume_step))  # actually point
        else:
            # estimate from spread
            point = Decimal("0.01")
        # Use symbol point if available from snapshot
        return Decimal(str(cfg.grid_distance_points)) * point

    def _build_intent(
        self,
        snapshot: MarketSnapshot,
        state: GridStrategyState,
        portfolio: PortfolioSnapshot,
        level: int,
    ) -> OrderIntent | None:
        cfg = self._cfg

        # Compute volume for this level
        vol = grid_lots_at_level(
            level=level,
            initial_lot=cfg.initial_lot,
            lot_mode=cfg.lot_mode,
            lot_multiplier=cfg.lot_multiplier,
            custom_lots=cfg.custom_lots,
            max_lot=cfg.max_lot,
            broker_spec=self._broker_spec,
        )

        if vol <= 0:
            return None

        # BUY at ask, SELL at bid
        price = snapshot.ask if cfg.direction == 0 else snapshot.bid

        comment = self._build_comment(state, level)

        return OrderIntent(
            symbol=cfg.symbol,
            direction=cfg.direction,
            volume=vol,
            intent_class=IntentClass.ENTRY,
            strategy_id=cfg.strategy_id,
            basket_id=state.basket_id,
            level=level,
            magic=cfg.magic,
            comment=comment,
            reason=f"grid_level_{level}",
            sl_points=cfg.protective_sl_points,
            config_hash=cfg.config_hash,
        )

    def _build_comment(self, state: GridStrategyState, level: int) -> str:
        from app.trading.baskets import build_comment
        import uuid
        return build_comment(
            strategy_short=self._cfg.strategy_id[:3],
            direction=self._cfg.basket_direction_name,
            basket_short=state.basket_id[:7],
            level=level,
            nonce=str(uuid.uuid4())[:4],
        )

    def on_fill(self, fill: Fill) -> None:
        state = self._state
        state.last_entry_price = fill.price_filled
        state.last_entry_time_monotonic = fill.monotonic_time
        state.position_count += 1
        state.waiting_for_first_entry = False
        log.info("strategy_fill_recorded",
                 basket_id=fill.basket_id, level=fill.level,
                 price=str(fill.price_filled), volume=str(fill.volume))

    def trigger_first_entry(self) -> None:
        """Called when user triggers manual first entry."""
        self._state.waiting_for_first_entry = False

    def state(self) -> dict:
        return self._state.to_dict()

    def disarm(self) -> None:
        self._state.armed = False

    def rearm(self) -> None:
        self._state.armed = True
        log.info("strategy_rearmed")

    def reset_basket(self) -> None:
        if self._cfg.rearm_after_basket_close:
            self._state.reset_for_new_basket()
            log.info("strategy_basket_reset", new_basket=self._state.basket_id)
        else:
            self.disarm()
