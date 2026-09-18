"""Account, Market, Positions, Trading, Strategy, Risk, Logs routes — Section 25."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from app.main import verify_token

router = APIRouter(tags=["account"], dependencies=[Depends(verify_token)])


@router.get("/account")
async def get_account() -> dict:
    from app.api.mt5_routes import _gateway
    if not _gateway:
        raise HTTPException(503, "MT5 not connected")
    try:
        account = _gateway.get_account()
        return account.to_dict()
    except Exception as e:
        raise HTTPException(503, str(e))
