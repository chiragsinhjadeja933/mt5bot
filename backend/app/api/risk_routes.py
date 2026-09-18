"""Risk config routes — Section 25 / 13."""
from fastapi import APIRouter, Depends
from app.main import verify_token

router = APIRouter(tags=["risk"], dependencies=[Depends(verify_token)])

_risk_config = {
    "max_daily_loss_pct": 5.0,
    "max_drawdown_pct": 10.0,
    "max_open_positions": 20,
    "max_total_volume": 2.0,
    "max_margin_usage_pct": 80.0,
    "min_margin_level_pct": 150.0,
    "max_spread_points": 100,
    "max_consecutive_losses": 5,
    "max_basket_loss": 50.0,
    "max_entries_per_hour": 20,
    "close_on_emergency": True,
}


@router.get("")
async def get_risk() -> dict:
    return _risk_config


@router.put("")
async def update_risk(config: dict) -> dict:
    _risk_config.update(config)
    return {"status": "updated", "config": _risk_config}
