"""Unit tests — lot sizing with Decimal (Section 12 [ADD], 30 [ADD])"""
from __future__ import annotations
from decimal import Decimal
import pytest
from app.trading.sizing import (
    BrokerVolumeSpec, TickSpec, round_volume, compute_risk_lots,
    validate_volume, grid_lots_at_level, worst_case_lots, calc_floating_pnl,
)

# Typical XAUUSD broker spec: 100 oz contract, lot step 0.01, digits 2
GOLD_SPEC = BrokerVolumeSpec(
    volume_min=Decimal("0.01"),
    volume_max=Decimal("50.0"),
    volume_step=Decimal("0.01"),
    volume_limit=Decimal("0"),
)

GOLD_TICK = TickSpec(
    tick_size=0.01,
    tick_value=1.0,       # per 0.01 price move per lot (simplified)
    tick_value_loss=1.0,
    trade_contract_size=100.0,
    point=0.01,
)


class TestRoundVolume:
    def test_exact_step(self):
        assert round_volume(Decimal("0.10"), GOLD_SPEC) == Decimal("0.10")

    def test_rounds_down_not_up(self):
        """0.015 rounds DOWN to 0.01 (step 0.01)."""
        assert round_volume(Decimal("0.015"), GOLD_SPEC) == Decimal("0.01")

    def test_float_artifact_avoided(self):
        """0.30000000000000004 → 0.30 (Decimal avoids float errors)."""
        result = round_volume(Decimal("0.30000000000000004"), GOLD_SPEC)
        assert result == Decimal("0.30")

    def test_clamps_to_min(self):
        result = round_volume(Decimal("0.001"), GOLD_SPEC)
        assert result == GOLD_SPEC.volume_min

    def test_clamps_to_max(self):
        result = round_volume(Decimal("999.0"), GOLD_SPEC)
        assert result == GOLD_SPEC.volume_max


class TestValidateVolume:
    def test_valid(self):
        assert validate_volume(Decimal("0.01"), GOLD_SPEC) == ""

    def test_below_min(self):
        err = validate_volume(Decimal("0.001"), GOLD_SPEC)
        assert "volume_min" in err

    def test_above_max(self):
        err = validate_volume(Decimal("999.0"), GOLD_SPEC)
        assert "volume_max" in err

    def test_not_aligned_to_step(self):
        err = validate_volume(Decimal("0.015"), GOLD_SPEC)
        assert "step" in err

    def test_total_lots_exceeded(self):
        err = validate_volume(
            Decimal("0.05"), GOLD_SPEC,
            current_total=Decimal("0.18"),
            max_total_lots=Decimal("0.20"),
        )
        assert "max_total_lots" in err


class TestGridLots:
    def test_fixed_same_at_every_level(self):
        for lvl in range(5):
            lot = grid_lots_at_level(lvl, Decimal("0.01"), "fixed",
                                     broker_spec=GOLD_SPEC)
            assert lot == Decimal("0.01")

    def test_multiplier_rounded_down(self):
        """0.01 × 1.5 = 0.015 → rounds to 0.01."""
        lot = grid_lots_at_level(1, Decimal("0.01"), "multiplier",
                                  lot_multiplier=1.5, broker_spec=GOLD_SPEC)
        assert lot == Decimal("0.01")

    def test_multiplier_larger(self):
        """0.01 × 2 = 0.02 → 0.02 (exact step)."""
        lot = grid_lots_at_level(1, Decimal("0.01"), "multiplier",
                                  lot_multiplier=2.0, broker_spec=GOLD_SPEC)
        assert lot == Decimal("0.02")

    def test_capped_at_max_lot(self):
        lot = grid_lots_at_level(10, Decimal("0.01"), "multiplier",
                                  lot_multiplier=3.0,
                                  max_lot=Decimal("0.05"),
                                  broker_spec=GOLD_SPEC)
        assert lot <= Decimal("0.05")

    def test_custom_lots(self):
        custom = [Decimal("0.01"), Decimal("0.02"), Decimal("0.04")]
        assert grid_lots_at_level(0, Decimal("0.01"), "custom", custom_lots=custom) == Decimal("0.01")
        assert grid_lots_at_level(2, Decimal("0.01"), "custom", custom_lots=custom) == Decimal("0.04")
        # Level beyond list → uses last
        assert grid_lots_at_level(9, Decimal("0.01"), "custom", custom_lots=custom) == Decimal("0.04")


class TestRiskLots:
    def test_basic(self):
        result = compute_risk_lots(
            risk_pct=Decimal("1.0"),
            account_equity=Decimal("10000"),
            stop_distance_points=100,
            tick_spec=GOLD_TICK,
            broker_spec=GOLD_SPEC,
        )
        # risk = 100; stop_ticks=100; lots = 100/(100*1.0) = 1.0
        assert result.reason_rejected == ""
        assert result.effective_lots > 0

    def test_below_volume_min(self):
        result = compute_risk_lots(
            risk_pct=Decimal("0.001"),
            account_equity=Decimal("100"),
            stop_distance_points=10000,
            tick_spec=GOLD_TICK,
            broker_spec=GOLD_SPEC,
        )
        assert result.reason_rejected != ""
        assert result.effective_lots == Decimal("0")


class TestFloatingPnl:
    def test_buy_profit(self):
        """BUY: price rises → profit."""
        pnl = calc_floating_pnl(
            price_open=Decimal("3600.00"),
            price_current=Decimal("3601.00"),
            volume=Decimal("0.01"),
            direction=0,
            tick_spec=GOLD_TICK,
        )
        assert pnl > 0

    def test_sell_profit(self):
        """SELL: price falls → profit."""
        pnl = calc_floating_pnl(
            price_open=Decimal("3600.00"),
            price_current=Decimal("3599.00"),
            volume=Decimal("0.01"),
            direction=1,
            tick_spec=GOLD_TICK,
        )
        assert pnl > 0

    def test_buy_loss(self):
        pnl = calc_floating_pnl(
            price_open=Decimal("3600.00"),
            price_current=Decimal("3599.00"),
            volume=Decimal("0.01"),
            direction=0,
            tick_spec=GOLD_TICK,
        )
        assert pnl < 0
