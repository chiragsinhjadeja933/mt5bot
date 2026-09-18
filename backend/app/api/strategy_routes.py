"""Strategy configuration routes — Section 25 / 22."""
from __future__ import annotations
import hashlib
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, validator
from app.main import verify_token

router = APIRouter(tags=["strategy"], dependencies=[Depends(verify_token)])

# In-memory strategy config (persisted to DB on save)
_current_strategy: dict = {
    "schema_version": 1,
    "strategy_id": "xauusd_fast_grid",
    "symbol": "XAUUSD",
    "symbol_broker_alias": None,
    "enabled": True,
    "mode": "DRY_RUN",
    "direction": "BUY",
    "grid_mode": "adverse",
    "grid_anchor": "last_entry",
    "first_entry": "immediate_on_start",
    "initial_lot": 0.01,
    "lot_mode": "fixed",
    "lot_multiplier": 1.0,
    "allow_multiplier": False,
    "custom_lots": [],
    "max_lot": 0.05,
    "max_total_lots": 0.50,
    "max_positions": 40,
    "grid_distance_points": 40,
    "basket_take_profit": 3.0,
    "basket_stop_loss": 50.0,
    "basket_pnl_basis": "net",
    "protective_sl_points": 5000,
    "max_slippage_points": 30,
    "max_spread_points": 60,
    "cooldown_seconds": 0,
    "rearm_after_basket_close": True,
    "rearm_delay_seconds": 5,
    "max_entries_per_hour": 100,
    "sessions": {"timezone": "UTC", "allowed": [["00:00", "23:59"]]},
    "aggressive_mode": True,
}


@router.get("")
async def get_strategy() -> dict:
    return _current_strategy


@router.post("")
async def update_strategy(config: dict) -> dict:
    global _current_strategy
    # Validate key fields
    required = {"strategy_id", "symbol", "direction", "initial_lot", "max_positions"}
    missing = required - set(config.keys())
    if missing:
        raise HTTPException(400, f"Missing required fields: {missing}")

    if config.get("lot_multiplier", 1.0) > 1.0 and not config.get("allow_multiplier", False):
        raise HTTPException(400,
            "lot_multiplier > 1.0 requires allow_multiplier=true. "
            "This is MARTINGALE/AVERAGING — HIGH RISK.")

    # Compute config hash
    config_str = json.dumps(config, sort_keys=True)
    config_hash = hashlib.sha256(config_str.encode()).hexdigest()[:16]
    config["_config_hash"] = config_hash

    _current_strategy = config
    return {"status": "saved", "config_hash": config_hash, "config": config}


@router.get("/exposure-preview")
async def exposure_preview() -> dict:
    """Worst-case exposure preview — Section 10 [FIX] point 7."""
    cfg = _current_strategy
    from decimal import Decimal
    from app.trading.sizing import worst_case_lots, BrokerVolumeSpec

    spec = BrokerVolumeSpec(
        volume_min=Decimal("0.01"),
        volume_max=Decimal(str(cfg.get("max_lot", 0.05))),
        volume_step=Decimal("0.01"),
        volume_limit=Decimal("0"),
    )

    lots = worst_case_lots(
        max_positions=cfg.get("max_positions", 20),
        initial_lot=Decimal(str(cfg.get("initial_lot", 0.01))),
        lot_mode=cfg.get("lot_mode", "fixed"),
        lot_multiplier=float(cfg.get("lot_multiplier", 1.0)),
        max_lot=Decimal(str(cfg.get("max_lot", 0.05))),
        broker_spec=spec,
    )

    return {
        "max_positions": cfg.get("max_positions"),
        "lots_per_level": [str(l) for l in lots],
        "total_lots": str(sum(lots)),
        "basket_sl": cfg.get("basket_stop_loss"),
        "warning": "Worst-case exposure only. Actual fills depend on market conditions.",
        "provenance": "DERIVED",
    }
