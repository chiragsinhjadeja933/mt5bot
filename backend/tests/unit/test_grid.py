"""Unit tests — Grid Strategy Engine (Section 10, 22)"""
from __future__ import annotations

from decimal import Decimal
import pytest

from app.trading.grid import (
    GridConfig,
    XAUUSDGridStrategy,
    MarketSnapshot,
    PortfolioSnapshot,
    Fill,
    IntentClass,
)
from app.trading.sizing import BrokerVolumeSpec


class MockClock:
    def __init__(self, start: float = 1000.0) -> None:
        self._time = start

    def advance(self, seconds: float) -> None:
        self._time += seconds

    def now_monotonic(self) -> float:
        return self._time

    def now_utc_timestamp(self) -> float:
        return self._time


@pytest.fixture
def broker_spec() -> BrokerVolumeSpec:
    return BrokerVolumeSpec(
        volume_min=Decimal("0.01"),
        volume_max=Decimal("100.0"),
        volume_step=Decimal("0.01"),
        volume_limit=Decimal("0"),
    )


@pytest.fixture
def default_config() -> GridConfig:
    return GridConfig(
        strategy_id="xauusd_grid",
        symbol="XAUUSD",
        direction=0,  # BUY
        grid_mode="adverse",
        grid_anchor="last_entry",
        first_entry="immediate_on_start",
        initial_lot=Decimal("0.01"),
        lot_mode="fixed",
        grid_distance_points=100,
        max_positions=5,
        max_spread_points=50,
        cooldown_seconds=10.0,
    )


class TestGridConfigValidation:
    def test_multiplier_requires_allow_flag(self):
        with pytest.raises(ValueError, match="requires allow_multiplier=true"):
            GridConfig(
                strategy_id="risky_grid",
                symbol="XAUUSD",
                direction=0,
                grid_mode="adverse",
                grid_anchor="last_entry",
                first_entry="immediate_on_start",
                initial_lot=Decimal("0.01"),
                lot_mode="multiplier",
                lot_multiplier=1.5,
                allow_multiplier=False,  # Disallowed
            )

    def test_multiplier_allowed_with_flag(self):
        cfg = GridConfig(
            strategy_id="risky_grid",
            symbol="XAUUSD",
            direction=0,
            grid_mode="adverse",
            grid_anchor="last_entry",
            first_entry="immediate_on_start",
            initial_lot=Decimal("0.01"),
            lot_mode="multiplier",
            lot_multiplier=1.5,
            allow_multiplier=True,
        )
        assert cfg.lot_multiplier == 1.5


class TestGridStrategyFirstEntry:
    def test_immediate_on_start_emits_level_0(self, default_config, broker_spec):
        strat = XAUUSDGridStrategy(default_config, broker_spec)
        clock = MockClock()
        snap = MarketSnapshot(
            symbol="XAUUSD",
            bid=Decimal("2650.00"),
            ask=Decimal("2650.30"),
            spread_points=30,
            timestamp_monotonic=clock.now_monotonic(),
        )
        port = PortfolioSnapshot(
            equity=Decimal("10000"),
            balance=Decimal("10000"),
            free_margin=Decimal("10000"),
            margin_level=Decimal("1000"),
            open_positions=0,
            total_volume=Decimal("0"),
        )
        intents = strat.on_market(snap, port, clock)
        assert len(intents) == 1
        assert intents[0].level == 0
        assert intents[0].intent_class == IntentClass.ENTRY
        assert intents[0].volume == Decimal("0.01")
        assert intents[0].direction == 0  # BUY

    def test_manual_trigger_first_entry_does_not_auto_emit(self, broker_spec):
        cfg = GridConfig(
            strategy_id="manual_grid",
            symbol="XAUUSD",
            direction=0,
            grid_mode="adverse",
            grid_anchor="last_entry",
            first_entry="manual_trigger",
            initial_lot=Decimal("0.01"),
            lot_mode="fixed",
        )
        strat = XAUUSDGridStrategy(cfg, broker_spec)
        clock = MockClock()
        snap = MarketSnapshot(
            symbol="XAUUSD",
            bid=Decimal("2650.00"),
            ask=Decimal("2650.30"),
            spread_points=30,
            timestamp_monotonic=clock.now_monotonic(),
        )
        port = PortfolioSnapshot(
            equity=Decimal("10000"),
            balance=Decimal("10000"),
            free_margin=Decimal("10000"),
            margin_level=Decimal("1000"),
            open_positions=0,
            total_volume=Decimal("0"),
        )
        intents = strat.on_market(snap, port, clock)
        assert len(intents) == 0


class TestGridStrategySubsequentLevels:
    def test_adverse_move_triggers_next_level_after_cooldown(self, default_config, broker_spec):
        strat = XAUUSDGridStrategy(default_config, broker_spec)
        clock = MockClock(1000.0)

        # Simulate first entry fill at 2650.30
        fill = Fill(
            basket_id="b1",
            level=0,
            direction=0,
            volume=Decimal("0.01"),
            price_filled=Decimal("2650.30"),
            ticket=12345,
            monotonic_time=clock.now_monotonic(),
        )
        strat.on_fill(fill)

        # Price drops 1.50 points (150 points drop)
        snap = MarketSnapshot(
            symbol="XAUUSD",
            bid=Decimal("2648.50"),
            ask=Decimal("2648.80"),  # drop of 1.50 from 2650.30 (more than 100 points = 1.00)
            spread_points=30,
            timestamp_monotonic=clock.now_monotonic(),
        )
        port = PortfolioSnapshot(
            equity=Decimal("9990"),
            balance=Decimal("10000"),
            free_margin=Decimal("9900"),
            margin_level=Decimal("800"),
            open_positions=1,
            total_volume=Decimal("0.01"),
        )

        # Before cooldown: should NOT trigger
        intents = strat.on_market(snap, port, clock)
        assert len(intents) == 0

        # Advance clock past cooldown (10 seconds)
        clock.advance(11.0)
        snap = MarketSnapshot(
            symbol="XAUUSD",
            bid=Decimal("2648.50"),
            ask=Decimal("2648.80"),
            spread_points=30,
            timestamp_monotonic=clock.now_monotonic(),
        )
        intents = strat.on_market(snap, port, clock)
        assert len(intents) == 1
        assert intents[0].level == 1
        assert intents[0].intent_class == IntentClass.ENTRY

    def test_spread_exceeding_max_blocks_entry(self, default_config, broker_spec):
        strat = XAUUSDGridStrategy(default_config, broker_spec)
        clock = MockClock()
        snap = MarketSnapshot(
            symbol="XAUUSD",
            bid=Decimal("2650.00"),
            ask=Decimal("2651.00"),
            spread_points=100,  # Exceeds max 50 points
            timestamp_monotonic=clock.now_monotonic(),
        )
        port = PortfolioSnapshot(
            equity=Decimal("10000"),
            balance=Decimal("10000"),
            free_margin=Decimal("10000"),
            margin_level=Decimal("1000"),
            open_positions=0,
            total_volume=Decimal("0"),
        )
        intents = strat.on_market(snap, port, clock)
        assert len(intents) == 0

    def test_max_positions_blocks_further_entries(self, default_config, broker_spec):
        strat = XAUUSDGridStrategy(default_config, broker_spec)
        clock = MockClock()
        # Set state position_count to max
        strat._state.position_count = default_config.max_positions
        strat._state.waiting_for_first_entry = False

        snap = MarketSnapshot(
            symbol="XAUUSD",
            bid=Decimal("2600.00"),
            ask=Decimal("2600.30"),
            spread_points=30,
            timestamp_monotonic=clock.now_monotonic(),
        )
        port = PortfolioSnapshot(
            equity=Decimal("9500"),
            balance=Decimal("10000"),
            free_margin=Decimal("9000"),
            margin_level=Decimal("500"),
            open_positions=5,
            total_volume=Decimal("0.05"),
        )
        intents = strat.on_market(snap, port, clock)
        assert len(intents) == 0
