"""Unit tests for GridTradingEngine."""
import asyncio
from decimal import Decimal
import pytest
from unittest.mock import MagicMock, AsyncMock

from app.trading.engine import GridTradingEngine
from app.mt5.gateway import OrderRequest, OrderResult
from app.trading.dryrun import VirtualPosition


class MockGateway:
    def __init__(self, tick_bid=4380.0, tick_ask=4380.3):
        self.tick_bid = tick_bid
        self.tick_ask = tick_ask
        self.positions = []
        self.orders_sent = []
        self.positions_closed = []

    def get_tick(self, symbol: str):
        mock_tick = MagicMock()
        mock_tick.bid = self.tick_bid
        mock_tick.ask = self.tick_ask
        mock_tick.spread_points = 30
        mock_tick.is_stale = False
        return mock_tick

    def get_positions(self, symbol=None, magic=None):
        return self.positions

    def send_order(self, request: OrderRequest) -> OrderResult:
        self.orders_sent.append(request)
        ticket = 1000 + len(self.positions)
        vpos = MagicMock()
        vpos.ticket = ticket
        vpos.symbol = request.symbol
        vpos.type = request.order_type
        vpos.volume = request.volume
        vpos.price_open = Decimal(str(request.price))
        vpos.profit = Decimal("0")
        vpos.swap = Decimal("0")
        vpos.entry_commission = Decimal("0")
        self.positions.append(vpos)
        return OrderResult(
            request=request,
            retcode=10009,
            retcode_name="DONE",
            order_ticket=ticket,
            deal_ticket=ticket,
            volume_filled=request.volume,
            price_filled=request.price,
            comment="FILLED",
            request_id=1,
            success=True,
            latency_ms=1.0,
            slippage_points=0,
            raw_result={},
        )

    def close_position(self, ticket, symbol, volume, order_type, price, deviation, magic, comment):
        self.positions_closed.append(ticket)
        self.positions = [p for p in self.positions if p.ticket != ticket]
        return MagicMock(success=True)


@pytest.mark.asyncio
async def test_engine_basket_tp_triggers_and_rearms():
    engine = GridTradingEngine()
    mock_gw = MockGateway()

    # Seed positions with profit totaling $3.50 (> $3.00 TP target)
    pos1 = MagicMock()
    pos1.ticket = 101
    pos1.type = 0
    pos1.symbol = "XAUUSD"
    pos1.volume = Decimal("0.01")
    pos1.price_open = Decimal("4380.00")
    pos1.profit = Decimal("2.00")
    pos1.swap = Decimal("0")
    pos1.entry_commission = Decimal("0")

    pos2 = MagicMock()
    pos2.ticket = 102
    pos2.type = 0
    pos2.symbol = "XAUUSD"
    pos2.volume = Decimal("0.01")
    pos2.price_open = Decimal("4380.50")
    pos2.profit = Decimal("1.50")
    pos2.swap = Decimal("0")
    pos2.entry_commission = Decimal("0")

    mock_gw.positions = [pos1, pos2]

    old_basket_id = engine.basket_id
    await engine._close_basket_positions(mock_gw, mock_gw.positions, "XAUUSD", 10001, "basket_tp")
    engine.reset_basket(reason="rearm_after_tp")

    assert len(mock_gw.positions_closed) == 2
    assert 101 in mock_gw.positions_closed
    assert 102 in mock_gw.positions_closed
    # Basket ID should reset for next cycle
    assert engine.basket_id != old_basket_id


@pytest.mark.asyncio
async def test_engine_first_entry_sent():
    engine = GridTradingEngine()
    mock_gw = MockGateway(tick_bid=4380.0, tick_ask=4380.3)

    cfg = {
        "strategy_id": "xauusd_fast_grid",
        "symbol": "XAUUSD",
        "direction": "BUY",
        "initial_lot": 0.01,
        "max_positions": 40,
        "grid_distance_points": 40,
        "max_slippage_points": 30,
        "magic": 10001,
        "first_entry": "immediate_on_start",
    }

    ok = await engine._send_grid_order(
        gw=mock_gw,
        symbol="XAUUSD",
        direction=0,
        volume=Decimal("0.01"),
        price=Decimal("4380.30"),
        magic=10001,
        comment="test_entry",
        level=0,
        cfg=cfg,
    )

    assert ok is True
    assert len(mock_gw.orders_sent) == 1
    assert mock_gw.orders_sent[0].volume == Decimal("0.01")
    assert mock_gw.orders_sent[0].order_type == 0
    assert engine._last_entry_price == Decimal("4380.30")
