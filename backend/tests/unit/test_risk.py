"""Unit tests — risk manager (Section 13 / 30 [ADD])"""
from __future__ import annotations
from decimal import Decimal
import pytest
from app.risk.manager import RiskManager, RiskConfig, RiskAction


def make_manager(**overrides) -> RiskManager:
    config = RiskConfig(**overrides)
    m = RiskManager(config)
    m.update_equity_baseline(Decimal("10000"))
    m.update_peak_equity(Decimal("10000"))
    return m


def default_check(m: RiskManager, **overrides) -> object:
    kwargs = dict(
        current_equity=Decimal("10000"),
        current_margin_level=Decimal("500"),
        current_spread_points=50,
        open_positions=5,
        total_volume=Decimal("0.5"),
        tick_age_ms=100.0,
        max_tick_age_ms=5000.0,
    )
    kwargs.update(overrides)
    return m.check_entry(**kwargs)


class TestRiskManagerAllow:
    def test_all_checks_pass(self):
        m = make_manager()
        verdict = default_check(m)
        assert verdict.allowed is True
        assert verdict.action == RiskAction.ALLOW

    def test_verdict_has_checks(self):
        m = make_manager()
        v = default_check(m)
        assert len(v.checks) > 0


class TestDailyLossLimit:
    def test_triggers_when_equity_drops(self):
        m = make_manager(max_daily_loss_pct=Decimal("5.0"))
        m.update_equity_baseline(Decimal("10000"))
        # Equity dropped 6% → should trigger
        v = default_check(m, current_equity=Decimal("9400"))
        assert v.allowed is False
        assert "daily_loss" in v.reason

    def test_does_not_trigger_within_limit(self):
        m = make_manager(max_daily_loss_pct=Decimal("5.0"))
        m.update_equity_baseline(Decimal("10000"))
        v = default_check(m, current_equity=Decimal("9600"))  # 4% loss
        assert v.allowed is True


class TestDrawdownLimit:
    def test_triggers_when_peak_exceeded(self):
        m = make_manager(max_drawdown_pct=Decimal("10.0"))
        m.update_peak_equity(Decimal("12000"))
        # Current=10000 → drawdown=16.7%
        v = default_check(m, current_equity=Decimal("10000"))
        assert v.allowed is False
        assert "drawdown" in v.reason


class TestSpreadLimit:
    def test_blocks_on_spread_spike(self):
        m = make_manager(max_spread_points=100)
        v = default_check(m, current_spread_points=150)
        assert v.allowed is False

    def test_allows_normal_spread(self):
        m = make_manager(max_spread_points=100)
        v = default_check(m, current_spread_points=50)
        assert v.allowed is True


class TestStaleDataFailsClosed:
    def test_stale_tick_blocks_entry(self):
        m = make_manager()
        v = default_check(m, tick_age_ms=6000.0, max_tick_age_ms=5000.0)
        assert v.allowed is False
        assert "tick_freshness" in v.reason


class TestLatchingLimits:
    def test_latched_limit_persists(self):
        m = make_manager(max_daily_loss_pct=Decimal("5.0"))
        m.update_equity_baseline(Decimal("10000"))
        # Trigger daily loss latch
        v1 = default_check(m, current_equity=Decimal("9400"))
        assert v1.latching is True
        # Even after equity "recovers", latch remains
        v2 = default_check(m, current_equity=Decimal("10000"))
        assert v2.allowed is False  # latch still active

    def test_manual_reset_clears_latch(self):
        m = make_manager(max_daily_loss_pct=Decimal("5.0"))
        m.update_equity_baseline(Decimal("10000"))
        default_check(m, current_equity=Decimal("9400"))  # trigger
        m.manual_reset_latch("daily_loss")
        v = default_check(m, current_equity=Decimal("10000"))
        assert v.allowed is True
