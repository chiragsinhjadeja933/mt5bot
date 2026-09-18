"""Unit tests — Basket Management (Section 11)"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import pytest

from app.trading.baskets import (
    Basket,
    BasketPosition,
    BasketState,
    build_comment,
    parse_basket_id_from_comment,
)


@pytest.fixture
def sample_positions() -> list[BasketPosition]:
    now = datetime.now(timezone.utc)
    return [
        BasketPosition(
            ticket=1001,
            direction=0,
            volume=Decimal("0.01"),
            price_open=Decimal("2650.00"),
            profit=Decimal("5.00"),
            swap=Decimal("-0.20"),
            entry_commission=Decimal("-0.05"),
            comment="xau|B|Babc123|L00|x1y2",
            level=0,
            open_time=now,
        ),
        BasketPosition(
            ticket=1002,
            direction=0,
            volume=Decimal("0.02"),
            price_open=Decimal("2645.00"),
            profit=Decimal("8.00"),
            swap=Decimal("-0.30"),
            entry_commission=Decimal("-0.10"),
            comment="xau|B|Babc123|L01|x3y4",
            level=1,
            open_time=now,
        ),
    ]


class TestBasketPnL:
    def test_total_volume(self, sample_positions):
        b = Basket(
            basket_id="abc12345",
            strategy_id="xau_grid",
            magic=100100,
            symbol="XAUUSD",
            direction=0,
            positions=sample_positions,
        )
        assert b.total_volume == Decimal("0.03")

    def test_weighted_avg_entry(self, sample_positions):
        b = Basket(
            basket_id="abc12345",
            strategy_id="xau_grid",
            magic=100100,
            symbol="XAUUSD",
            direction=0,
            positions=sample_positions,
        )
        # (0.01 * 2650 + 0.02 * 2645) / 0.03 = (26.50 + 52.90) / 0.03 = 79.40 / 0.03 = 2646.666...
        expected = (Decimal("0.01") * Decimal("2650.00") + Decimal("0.02") * Decimal("2645.00")) / Decimal("0.03")
        assert b.weighted_avg_entry == expected

    def test_floating_gross_and_net(self, sample_positions):
        b = Basket(
            basket_id="abc12345",
            strategy_id="xau_grid",
            magic=100100,
            symbol="XAUUSD",
            direction=0,
            positions=sample_positions,
            pnl_basis="net",
        )
        # Gross: (5.00 - 0.20) + (8.00 - 0.30) = 4.80 + 7.70 = 12.50
        assert b.floating_gross == Decimal("12.50")
        # Entry commission: -0.05 + -0.10 = -0.15
        assert b.entry_commissions == Decimal("-0.15")
        # Net: 12.50 - 0.15 = 12.35
        assert b.floating_net == Decimal("12.35")
        assert b.current_pnl == Decimal("12.35")


class TestBasketTpSl:
    def test_should_take_profit(self, sample_positions):
        b = Basket(
            basket_id="abc12345",
            strategy_id="xau_grid",
            magic=100100,
            symbol="XAUUSD",
            direction=0,
            positions=sample_positions,
            basket_tp=Decimal("10.00"),
            basket_sl=Decimal("50.00"),
            pnl_basis="net",
        )
        # Current net PnL is 12.35 >= 10.00 -> Should TP
        assert b.should_take_profit() is True
        assert b.should_stop_loss() is False

    def test_should_stop_loss(self):
        now = datetime.now(timezone.utc)
        losing_pos = [
            BasketPosition(
                ticket=1001,
                direction=0,
                volume=Decimal("0.01"),
                price_open=Decimal("2650.00"),
                profit=Decimal("-55.00"),
                swap=Decimal("-1.00"),
                entry_commission=Decimal("-0.10"),
                comment="test",
                level=0,
                open_time=now,
            )
        ]
        b = Basket(
            basket_id="loss_basket",
            strategy_id="xau_grid",
            magic=100100,
            symbol="XAUUSD",
            direction=0,
            positions=losing_pos,
            basket_tp=Decimal("15.00"),
            basket_sl=Decimal("50.00"),
            pnl_basis="net",
        )
        # PnL = -55 - 1 - 0.10 = -56.10 <= -50 -> Should SL
        assert b.should_stop_loss() is True
        assert b.should_take_profit() is False

    def test_no_trigger_if_not_active(self, sample_positions):
        b = Basket(
            basket_id="abc12345",
            strategy_id="xau_grid",
            magic=100100,
            symbol="XAUUSD",
            direction=0,
            positions=sample_positions,
            basket_tp=Decimal("10.00"),
            state=BasketState.CLOSING,  # Already closing
        )
        assert b.should_take_profit() is False


class TestCommentEncoding:
    def test_build_and_parse_comment(self):
        comment = build_comment(
            strategy_short="XAU",
            direction="BUY",
            basket_short="b123456",
            level=3,
            nonce="a9f2",
        )
        assert len(comment) <= 31
        basket_id, level = parse_basket_id_from_comment(comment)
        assert basket_id == "b123456"
        assert level == 3

    def test_parse_invalid_comment_fails_safely(self):
        basket_id, level = parse_basket_id_from_comment("manual order from terminal")
        assert basket_id is None
        assert level is None
