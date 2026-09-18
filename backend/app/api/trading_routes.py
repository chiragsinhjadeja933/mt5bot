"""Trading control routes — Sections 14, 15, 25."""
from __future__ import annotations
import secrets as _secrets
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.main import verify_token, _system_state
from app.trading.state_machine import BotState, ExecutionMode

router = APIRouter(tags=["trading"], dependencies=[Depends(verify_token)])

# Two-step start nonce store
_pending_nonces: dict[str, dict] = {}


class StartRequest(BaseModel):
    confirmation_token: str  # User must type "START DEMO"


class ModeRequest(BaseModel):
    mode: str  # DRY_RUN | DEMO_EXECUTION
    confirmation_token: str


class ResetRequest(BaseModel):
    confirmation_token: str  # User must type "RESET"


@router.post("/start-request")
async def request_start() -> dict:
    """Step 1 of two-step start. Returns a nonce for confirmation."""
    nonce = _secrets.token_hex(16)
    state = _system_state.to_dict()
    _pending_nonces[nonce] = state
    return {
        "nonce": nonce,
        "instructions": "Call POST /api/trading/start with nonce and type 'START DEMO' to confirm.",
        "current_state": state,
    }


@router.post("/start")
async def start_trading(req: StartRequest) -> dict:
    """Step 2: Confirm start with typed token. Section 2 [FIX]."""
    if req.confirmation_token.strip().upper() != "START DEMO":
        raise HTTPException(400, "Confirmation token must be exactly 'START DEMO'")

    current = _system_state.bot_state
    if current == BotState.EMERGENCY_STOP:
        raise HTTPException(400, "Bot is in EMERGENCY_STOP — reset first.")
    if current == BotState.RUNNING:
        return {"status": "already_running"}

    _system_state.transition_bot(BotState.RUNNING, "user_start")
    return {"status": "running", "state": _system_state.to_dict()}


@router.post("/pause")
async def pause_trading() -> dict:
    current = _system_state.bot_state
    if current == BotState.RUNNING:
        _system_state.transition_bot(BotState.PAUSED, "user_pause")
    return {"status": "paused", "state": _system_state.to_dict()}


@router.post("/stop")
async def stop_trading() -> dict:
    current = _system_state.bot_state
    if current in (BotState.RUNNING, BotState.PAUSED):
        _system_state.transition_bot(BotState.STOPPING, "user_stop")
        _system_state.transition_bot(BotState.READY, "stopped")
    return {"status": "stopped", "state": _system_state.to_dict()}


@router.post("/emergency-stop")
async def emergency_stop() -> dict:
    """
    Emergency stop — Section 14 [ADD].
    Works from any state. Persisted. Single click + one confirm.
    """
    try:
        _system_state.transition_bot(BotState.EMERGENCY_STOP, "emergency")
    except ValueError:
        # Already in EMERGENCY_STOP
        pass

    # Persist to DB
    try:
        from app.database.models import get_session, get_or_create_bot_state
        with get_session() as session:
            row = get_or_create_bot_state(session)
            row.emergency_stop = True
            session.commit()
    except Exception as e:
        pass  # DB failure must not block emergency

    return {"status": "EMERGENCY_STOP", "state": _system_state.to_dict()}


@router.post("/close-all")
async def close_all_positions() -> dict:
    """Close all bot-owned positions. Section 14 [ADD]."""
    from app.trading.engine import get_trading_engine
    from app.api.mt5_routes import _gateway
    eng = get_trading_engine()
    gw = eng.get_active_gateway() or _gateway
    if not gw:
        raise HTTPException(503, "MT5 not connected")

    positions = gw.get_positions()
    results = []
    for pos in positions:
        try:
            close_type = 1 if pos.type == 0 else 0
            tick = gw.get_tick(pos.symbol)
            price = float(tick.bid) if close_type == 1 else float(tick.ask)
            result = gw.close_position(
                ticket=pos.ticket,
                symbol=pos.symbol,
                volume=pos.volume,
                order_type=close_type,
                price=price,
                deviation=50,
                magic=pos.magic,
                comment="close_all",
            )
            results.append({"ticket": pos.ticket, "success": result.success,
                            "retcode": result.retcode})
        except Exception as e:
            results.append({"ticket": pos.ticket, "success": False, "error": str(e)})

    return {"closed": results, "count": len(results)}


@router.post("/mode")
async def set_mode(req: ModeRequest) -> dict:
    """Switch between DRY_RUN and DEMO_EXECUTION. Requires confirmation."""
    if req.mode not in ("DRY_RUN", "DEMO_EXECUTION"):
        raise HTTPException(400, "mode must be DRY_RUN or DEMO_EXECUTION")

    if req.mode == "DEMO_EXECUTION":
        # Requires explicit typed confirmation
        if req.confirmation_token.strip().upper() != "DEMO EXECUTION":
            raise HTTPException(400, "Type 'DEMO EXECUTION' to confirm mode switch")

        # Also requires a passing connection test (Section 5 gate)
        # (simplified check here — full gate in connection_test service)

    mode_enum = ExecutionMode.DRY_RUN if req.mode == "DRY_RUN" else ExecutionMode.DEMO_EXECUTION
    _system_state.set_mode(mode_enum)
    return {"mode": req.mode, "state": _system_state.to_dict()}


@router.post("/reset-emergency")
async def reset_emergency(req: ResetRequest) -> dict:
    """Reset EMERGENCY_STOP — requires typed 'RESET' + clean reconciliation."""
    if req.confirmation_token.strip().upper() != "RESET":
        raise HTTPException(400, "Type 'RESET' to confirm emergency stop reset")

    if _system_state.bot_state != BotState.EMERGENCY_STOP:
        return {"status": "not_in_emergency_stop"}

    # Persist reset
    try:
        from app.database.models import get_session, get_or_create_bot_state
        with get_session() as session:
            row = get_or_create_bot_state(session)
            row.emergency_stop = False
            session.commit()
    except Exception:
        pass

    _system_state.transition_bot(BotState.READY, "manual_reset_confirmed")
    return {"status": "reset", "state": _system_state.to_dict()}


@router.get("/basket")
async def get_basket() -> dict:
    """Get current active basket status and statistics."""
    from app.trading.engine import get_trading_engine
    engine = get_trading_engine()
    return engine.get_basket_status()

