"""MT5 connection routes — Section 25."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.main import _system_state, verify_token
from app.config import get_settings

router = APIRouter(tags=["mt5"], dependencies=[Depends(verify_token)])

_connection = None
_gateway = None


class ConnectResponse(BaseModel):
    status: str
    login: int | None = None
    server: str | None = None
    account_type: str | None = None
    currency: str | None = None
    balance: str | None = None
    equity: str | None = None
    leverage: int | None = None
    margin_mode: str | None = None
    message: str = ""


@router.post("/connect", response_model=ConnectResponse)
async def connect_mt5() -> ConnectResponse:
    """Connect to MT5 terminal. Idempotent."""
    global _connection, _gateway
    settings = get_settings()

    if _connection and _connection.is_initialized:
        info = _connection.connection_info
        if info:
            from app.trading.state_machine import ConnectionState
            from app.websocket.ws_handler import start_broadcaster
            if _system_state.connection_state != ConnectionState.CONNECTED:
                _system_state.transition_connection(ConnectionState.CONNECTED, "connected")
            start_broadcaster(settings.gold_symbol)
            return ConnectResponse(
                status="ALREADY_CONNECTED",
                login=info.login,
                server=info.server,
                account_type="DEMO" if info.trade_mode == 0 else "REAL",
                currency=info.currency,
                balance=str(info.balance),
                equity=str(info.equity),
                leverage=info.leverage,
                margin_mode="HEDGING" if info.margin_mode == 2 else "NETTING",
            )

    try:
        from app.mt5.connection import MT5Connection
        from app.mt5.gateway import Mt5Gateway
        from app.trading.state_machine import ConnectionState
        from app.websocket.ws_handler import start_broadcaster

        _system_state.transition_connection(ConnectionState.CONNECTING, "user_connect")

        conn = MT5Connection(
            terminal_path=settings.mt5_terminal_path,
            login=settings.mt5_login,
            password=settings.mt5_password.get_secret_value() if settings.mt5_password else None,
            server=settings.mt5_server,
            timeout_ms=settings.mt5_timeout_ms,
            allowed_login=settings.allowed_login,
        )
        info = conn.initialize()
        _connection = conn
        _gateway = Mt5Gateway(conn)

        _system_state.transition_connection(ConnectionState.CONNECTED, "connected")
        start_broadcaster(settings.gold_symbol)

        return ConnectResponse(
            status="CONNECTED",
            login=info.login,
            server=info.server,
            account_type="DEMO" if info.trade_mode == 0 else "REAL",
            currency=info.currency,
            balance=str(info.balance),
            equity=str(info.equity),
            leverage=info.leverage,
            margin_mode="HEDGING" if info.margin_mode == 2 else "NETTING",
        )

    except Exception as e:
        from app.trading.state_machine import ConnectionState
        _system_state.transition_connection(ConnectionState.ERROR, str(e))
        raise HTTPException(status_code=503, detail={
            "code": "MT5_CONNECT_FAILED",
            "message": str(e),
            "fix": "Ensure MT5 terminal is running, logged in to DEMO, and Algo Trading is enabled.",
        })


@router.get("/status")
async def mt5_status() -> dict:
    global _connection
    if not _connection or not _connection.is_initialized:
        return {"connected": False, "state": _system_state.display_state}
    try:
        health = _connection.health_check()
        info = _connection.connection_info
        return {
            "connected": health.get("ok", False),
            "state": _system_state.display_state,
            "health": health,
            "login": info.login if info else None,
            "server": info.server if info else None,
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}


@router.post("/disconnect")
async def disconnect_mt5() -> dict:
    global _connection, _gateway
    if _connection:
        _connection.shutdown()
        _connection = None
        _gateway = None
    from app.trading.state_machine import ConnectionState
    _system_state.transition_connection(ConnectionState.DISCONNECTED, "user_disconnect")
    return {"status": "disconnected"}


@router.post("/test")
async def run_connection_test() -> dict:
    """
    Run the full MT5 connection test (Section 5).
    Requires user confirmation (passed in body). Returns per-stage results.
    """
    global _connection, _gateway
    if not _connection or not _connection.is_initialized:
        raise HTTPException(status_code=503, detail="MT5 not connected")

    from app.services.connection_test import run_full_test
    result = await run_full_test(_connection, _gateway)
    return result


@router.get("/test/latest")
async def get_latest_test() -> dict:
    """Return the latest connection test result from DB."""
    from app.database.models import get_session, ConnectionTest
    with get_session() as session:
        row = session.query(ConnectionTest).order_by(ConnectionTest.tested_at.desc()).first()
        if row is None:
            return {"found": False}
        stages = json.loads(row.stages_json or "{}")
        return {
            "found": True,
            "login": row.login,
            "server": row.server,
            "passed": row.overall_passed,
            "tested_at": row.tested_at.isoformat() if row.tested_at else None,
            "stages": stages,
        }
