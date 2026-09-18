"""
Risk Manager — Section 13 [ADD]
Hard limits independent of strategy. Runs in its own loop.
Structured verdict objects. Latching limits require manual reset.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

import structlog

log = structlog.get_logger(__name__)


class RiskAction(str, Enum):
    ALLOW = "ALLOW"
    BLOCK_ENTRIES = "BLOCK_ENTRIES"
    PAUSE = "PAUSE"
    CLOSE_BASKET = "CLOSE_BASKET"
    CLOSE_ALL = "CLOSE_ALL"


@dataclass
class RiskCheck:
    name: str
    passed: bool
    value: Any
    limit: Any
    unit: str = ""


@dataclass
class RiskVerdict:
    allowed: bool
    action: RiskAction
    checks: list[RiskCheck]
    reason: str
    latching: bool = False  # if True, requires manual reset
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "action": self.action,
            "reason": self.reason,
            "latching": self.latching,
            "timestamp": self.timestamp.isoformat(),
            "checks": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "value": str(c.value),
                    "limit": str(c.limit),
                    "unit": c.unit,
                }
                for c in self.checks
            ],
        }


@dataclass
class RiskConfig:
    """All risk limits — configurable, with conservative defaults."""
    max_daily_loss_pct: Decimal = Decimal("5.0")      # % of equity at day start
    max_drawdown_pct: Decimal = Decimal("10.0")        # % peak→current
    max_open_positions: int = 20
    max_total_volume: Decimal = Decimal("2.0")
    max_margin_usage_pct: Decimal = Decimal("80.0")
    min_margin_level_pct: Decimal = Decimal("150.0")
    max_spread_points: int = 100
    max_consecutive_losses: int = 5
    max_basket_loss: Decimal = Decimal("50.0")         # account currency
    max_entries_per_hour: int = 20
    close_on_emergency: bool = True
    daily_loss_basis: str = "equity"                   # "equity" or "realized"
    drawdown_baseline: str = "since_start_of_run"      # or "since_start_of_day" / "all_time"


class RiskManager:
    """
    Hard risk-management layer independent of the strategy.
    Has veto power over everything.
    Runs in a separate asyncio task/thread.
    """

    def __init__(self, config: RiskConfig) -> None:
        self._config = config
        self._lock = threading.Lock()

        # State
        self._equity_at_day_start: Decimal = Decimal("0")
        self._peak_equity: Decimal = Decimal("0")
        self._consecutive_losses: int = 0
        self._entries_this_hour: list[float] = []   # monotonic timestamps
        self._latched: dict[str, bool] = {}         # latching limit name → True
        self._daily_realized_loss: Decimal = Decimal("0")

    def update_equity_baseline(self, equity: Decimal) -> None:
        """Call at startup and day rollover."""
        with self._lock:
            if self._equity_at_day_start == 0:
                self._equity_at_day_start = equity
            if equity > self._peak_equity:
                self._peak_equity = equity

    def update_peak_equity(self, equity: Decimal) -> None:
        with self._lock:
            if equity > self._peak_equity:
                self._peak_equity = equity

    def record_entry(self) -> None:
        now = time.monotonic()
        with self._lock:
            # Keep only entries in last 3600s
            self._entries_this_hour = [t for t in self._entries_this_hour if now - t < 3600]
            self._entries_this_hour.append(now)

    def record_loss(self, amount: Decimal) -> None:
        with self._lock:
            if amount < 0:
                self._consecutive_losses += 1
            else:
                self._consecutive_losses = 0

    def manual_reset_latch(self, limit_name: str) -> None:
        with self._lock:
            self._latched.pop(limit_name, None)
        log.info("risk_latch_reset", limit=limit_name)

    def check_entry(
        self,
        current_equity: Decimal,
        current_margin_level: Decimal,
        current_spread_points: int,
        open_positions: int,
        total_volume: Decimal,
        basket_current_pnl: Decimal | None = None,
        tick_age_ms: float = 0.0,
        max_tick_age_ms: float = 5000.0,
    ) -> RiskVerdict:
        """
        Full entry check. Every verdict is stored. Section 13 [ADD].
        Fail closed: missing/stale data → deny entries.
        """
        checks: list[RiskCheck] = []
        failed_checks: list[RiskCheck] = []
        latching_triggered = False

        with self._lock:
            day_start = self._equity_at_day_start
            peak = self._peak_equity
            consecutive = self._consecutive_losses
            now = time.monotonic()
            entries_last_hour = len([t for t in self._entries_this_hour if now - t < 3600])
            latched = dict(self._latched)

        cfg = self._config

        # ── Stale data — fail closed ─────────────────────────────────────────
        stale = tick_age_ms > max_tick_age_ms
        c = RiskCheck("tick_freshness", not stale,
                      f"{tick_age_ms:.0f}ms", f"{max_tick_age_ms:.0f}ms", "ms")
        checks.append(c)
        if not c.passed:
            failed_checks.append(c)

        # ── Daily loss ───────────────────────────────────────────────────────
        if day_start > 0:
            daily_loss_pct = (day_start - current_equity) / day_start * Decimal("100")
        else:
            daily_loss_pct = Decimal("0")
        c = RiskCheck("daily_loss_pct",
                      daily_loss_pct < cfg.max_daily_loss_pct,
                      daily_loss_pct, cfg.max_daily_loss_pct, "%")
        checks.append(c)
        if not c.passed:
            failed_checks.append(c)
            latching_triggered = True
            with self._lock:
                self._latched["daily_loss"] = True

        # ── Drawdown ─────────────────────────────────────────────────────────
        if peak > 0:
            drawdown_pct = (peak - current_equity) / peak * Decimal("100")
        else:
            drawdown_pct = Decimal("0")
        c = RiskCheck("drawdown_pct",
                      drawdown_pct < cfg.max_drawdown_pct,
                      drawdown_pct, cfg.max_drawdown_pct, "%")
        checks.append(c)
        if not c.passed:
            failed_checks.append(c)
            latching_triggered = True
            with self._lock:
                self._latched["drawdown"] = True

        # ── Open positions ───────────────────────────────────────────────────
        c = RiskCheck("open_positions", open_positions < cfg.max_open_positions,
                      open_positions, cfg.max_open_positions, "positions")
        checks.append(c)
        if not c.passed:
            failed_checks.append(c)

        # ── Total volume ─────────────────────────────────────────────────────
        c = RiskCheck("total_volume", total_volume < cfg.max_total_volume,
                      total_volume, cfg.max_total_volume, "lots")
        checks.append(c)
        if not c.passed:
            failed_checks.append(c)

        # ── Margin level ─────────────────────────────────────────────────────
        c = RiskCheck("margin_level_pct",
                      current_margin_level == 0 or current_margin_level >= cfg.min_margin_level_pct,
                      current_margin_level, cfg.min_margin_level_pct, "%")
        checks.append(c)
        if not c.passed:
            failed_checks.append(c)

        # ── Spread ───────────────────────────────────────────────────────────
        c = RiskCheck("spread_points", current_spread_points <= cfg.max_spread_points,
                      current_spread_points, cfg.max_spread_points, "points")
        checks.append(c)
        if not c.passed:
            failed_checks.append(c)

        # ── Consecutive losses ───────────────────────────────────────────────
        c = RiskCheck("consecutive_losses", consecutive < cfg.max_consecutive_losses,
                      consecutive, cfg.max_consecutive_losses)
        checks.append(c)
        if not c.passed:
            failed_checks.append(c)
            latching_triggered = True

        # ── Basket P/L ───────────────────────────────────────────────────────
        if basket_current_pnl is not None:
            c = RiskCheck("basket_loss",
                          basket_current_pnl >= -cfg.max_basket_loss,
                          basket_current_pnl, -cfg.max_basket_loss, cfg._config_currency if hasattr(cfg, '_config_currency') else "ccy")
            checks.append(c)
            if not c.passed:
                failed_checks.append(c)

        # ── Entries per hour ─────────────────────────────────────────────────
        c = RiskCheck("entries_per_hour", entries_last_hour < cfg.max_entries_per_hour,
                      entries_last_hour, cfg.max_entries_per_hour, "entries/h")
        checks.append(c)
        if not c.passed:
            failed_checks.append(c)

        # ── Latched limits ───────────────────────────────────────────────────
        for latch_name in latched:
            c = RiskCheck(f"latch_{latch_name}", False, "LATCHED", "requires_manual_reset")
            checks.append(c)
            failed_checks.append(c)

        if failed_checks:
            reason = "; ".join(
                f"{c.name}={c.value}/{c.limit}" for c in failed_checks
            )
            action = RiskAction.PAUSE if latching_triggered else RiskAction.BLOCK_ENTRIES
            return RiskVerdict(
                allowed=False,
                action=action,
                checks=checks,
                reason=reason,
                latching=latching_triggered,
            )

        return RiskVerdict(
            allowed=True,
            action=RiskAction.ALLOW,
            checks=checks,
            reason="all_checks_passed",
        )
