"""Positions routes — Section 25 / 7."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.main import verify_token

router = APIRouter(tags=["positions"], dependencies=[Depends(verify_token)])


class ModifyRequest(BaseModel):
    sl: float = 0.0
    tp: float = 0.0


@router.get("/positions")
async def get_positions() -> list:
    from app.trading.engine import get_trading_engine
    from app.api.mt5_routes import _gateway
    eng = get_trading_engine()
    gw = eng.get_active_gateway() or _gateway
    if not gw:
        raise HTTPException(503, "MT5 not connected")
    positions = gw.get_positions()
    return [p.to_dict() for p in positions]


@router.post("/positions/{ticket}/close")
async def close_position(ticket: int) -> dict:
    from app.trading.engine import get_trading_engine
    from app.api.mt5_routes import _gateway
    eng = get_trading_engine()
    gw = eng.get_active_gateway() or _gateway
    if not gw:
        raise HTTPException(503, "MT5 not connected")
    positions = gw.get_positions()
    pos = next((p for p in positions if p.ticket == ticket), None)
    if pos is None:
        raise HTTPException(404, f"Position {ticket} not found")

    # Close: opposite direction
    close_type = 1 if pos.type == 0 else 0  # BUY→SELL, SELL→BUY
    tick = gw.get_tick(pos.symbol)
    price = float(tick.bid) if close_type == 1 else float(tick.ask)

    result = _gateway.close_position(
        ticket=ticket,
        symbol=pos.symbol,
        volume=pos.volume,
        order_type=close_type,
        price=price,
        deviation=30,
        magic=pos.magic,
        comment="manual_close",
    )
    return result.to_dict()


@router.put("/positions/{ticket}")
async def modify_position(ticket: int, req: ModifyRequest) -> dict:
    from app.api.mt5_routes import _gateway
    if not _gateway:
        raise HTTPException(503, "MT5 not connected")
    success = _gateway.modify_position(ticket, req.sl, req.tp)
    return {"success": success, "ticket": ticket}


@router.get("/orders")
async def get_orders() -> list:
    """Pending orders from MT5."""
    from app.api.mt5_routes import _connection
    if not _connection:
        raise HTTPException(503, "MT5 not connected")
    def _do():
        import MetaTrader5 as mt5
        orders = mt5.orders_get() or []
        return [
            {
                "ticket": o.ticket,
                "symbol": o.symbol,
                "type": o.type,
                "volume_initial": o.volume_initial,
                "volume_current": o.volume_current,
                "price_open": o.price_open,
                "sl": o.sl,
                "tp": o.tp,
                "magic": o.magic,
                "comment": o.comment,
            }
            for o in orders
        ]
    return _connection._run_in_worker(_do)


@router.get("/history")
async def get_history(
    from_date: str | None = None,
    to_date: str | None = None,
    symbol: str | None = None,
) -> list:
    from app.api.mt5_routes import _connection
    if not _connection:
        raise HTTPException(503, "MT5 not connected")
    from datetime import datetime, timezone, timedelta
    from app.mt5.history import get_deals_range

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=30)
    if from_date:
        start = datetime.fromisoformat(from_date).replace(tzinfo=timezone.utc)
    end = now
    if to_date:
        end = datetime.fromisoformat(to_date).replace(tzinfo=timezone.utc)

    def _do():
        deals = get_deals_range(start, end, _connection.mt5)
        result = [d.to_dict() for d in deals]
        if symbol:
            result = [d for d in result if d.get("symbol", "").upper() == symbol.upper()]
        return result

    return _connection._run_in_worker(_do)
