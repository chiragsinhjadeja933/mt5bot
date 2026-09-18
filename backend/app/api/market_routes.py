"""Market data routes — Section 25 / 18."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from app.main import verify_token
from app.config import get_settings

router = APIRouter(tags=["market"], dependencies=[Depends(verify_token)])


@router.get("/xauusd")
async def get_xauusd() -> dict:
    from app.api.mt5_routes import _gateway
    if not _gateway:
        raise HTTPException(503, "MT5 not connected")
    settings = get_settings()
    try:
        tick = _gateway.get_tick(settings.gold_symbol)
        return tick.to_dict()
    except Exception as e:
        raise HTTPException(503, str(e))


@router.get("/{symbol}")
async def get_market(symbol: str) -> dict:
    from app.api.mt5_routes import _gateway
    if not _gateway:
        raise HTTPException(503, "MT5 not connected")
    try:
        tick = _gateway.get_tick(symbol.upper())
        return tick.to_dict()
    except Exception as e:
        raise HTTPException(503, str(e))
