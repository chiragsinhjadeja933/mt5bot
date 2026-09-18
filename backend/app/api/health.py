"""Health check endpoint — Section 25."""
from fastapi import APIRouter
from datetime import datetime, timezone

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    from app.main import _system_state
    from app.trading.engine import get_trading_engine
    eng = get_trading_engine()
    basket = eng.get_basket_status()

    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "connection_state": _system_state.connection_state,
        "bot_state": _system_state.bot_state,
        "execution_mode": _system_state.execution_mode,
        "basket": {
            "id": basket.get("basket_id"),
            "positions": basket.get("position_count"),
            "floating_pnl": basket.get("floating_pnl"),
            "target_tp": basket.get("basket_tp"),
        },
        "version": "1.0.0",
        "demo_only": True,
    }
