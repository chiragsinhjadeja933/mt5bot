"""
FastAPI Application — MT5 Demo Trading Terminal
Section 25, 34, 37.
Binds to 127.0.0.1 by default.
API token auth on all endpoints.
Single uvicorn worker (MT5 state is process-local).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

import structlog
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.database.models import init_db, get_session, get_or_create_bot_state
from app.trading.state_machine import SystemState, ConnectionState, BotState, ExecutionMode

# ── Logging Setup ─────────────────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
log = structlog.get_logger(__name__)

# ── Shared application state ──────────────────────────────────────────────────
_system_state = SystemState()
_mt5_connection = None
_mt5_gateway = None
_dryrun_gateway = None
_market_data_task: asyncio.Task | None = None

settings = get_settings()


# ── Instance lock (prevent two bots on same account) ─────────────────────────
_LOCK_FILE = Path("mt5terminal.lock")


def acquire_instance_lock() -> None:
    if _LOCK_FILE.exists():
        content = _LOCK_FILE.read_text().strip()
        try:
            pid = int(content)
            # Check if that PID is still running
            os.kill(pid, 0)
            print(f"\n[FATAL] Another instance is running (PID {pid}). "
                  f"Two bots on one account cause duplicate orders. "
                  f"Stop the other instance first.\n", file=sys.stderr)
            sys.exit(1)
        except (OSError, ProcessLookupError):
            pass  # old lock file, safe to overwrite
    _LOCK_FILE.write_text(str(os.getpid()))


def release_instance_lock() -> None:
    try:
        _LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass


# ── Auth ──────────────────────────────────────────────────────────────────────
_security = HTTPBearer(auto_error=False)


def verify_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
) -> None:
    """API token auth on every request. Section 34 [ADD]."""
    expected = settings.api_token.get_secret_value()
    # Allow WebSocket upgrade without auth check here (handled in WS endpoint)
    token = None
    if credentials:
        token = credentials.credentials
    # Also allow via query param for WebSocket clients
    if not token:
        token = request.query_params.get("token")
    if not token or not secrets.compare_digest(token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token",
        )


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    log.info("startup_begin", version="1.0.0", mode="DEMO_ONLY_V1")

    # Instance lock
    acquire_instance_lock()

    # Database
    init_db(settings.database_url)

    # Restore persisted bot state
    with get_session() as session:
        bot_row = get_or_create_bot_state(session)
        if bot_row.emergency_stop:
            _system_state.transition_bot(BotState.EMERGENCY_STOP, "persisted_from_db")
            log.warning("startup_emergency_stop_persisted",
                        msg="Bot was in EMERGENCY_STOP. Manual reset required.")

    log.info("startup_ready",
             host=settings.backend_host,
             port=settings.backend_port,
             api_token_hint=f"...{settings.api_token.get_secret_value()[-8:]}",
             default_mode=settings.default_mode)

    yield

    # Shutdown
    log.info("shutdown_begin")
    if _market_data_task and not _market_data_task.done():
        _market_data_task.cancel()
    if _mt5_connection:
        try:
            _mt5_connection.shutdown()
        except Exception as e:
            log.warning("mt5_shutdown_error", error=str(e))
    release_instance_lock()
    log.info("shutdown_complete")


# ── App Factory ───────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title="MT5 Demo Trading Terminal",
        description="Automated XAUUSD trading bot — DEMO ONLY",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # CORS — restricted to configured frontend origin
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Error handler ─────────────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled_exception", path=request.url.path, error=str(exc))
        return JSONResponse(
            status_code=500,
            content={
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred",
                "details": {},
                "correlation_id": "",
            },
        )

    # ── Register routers ──────────────────────────────────────────────────
    from app.api.health import router as health_router
    from app.api.mt5_routes import router as mt5_router
    from app.api.account_routes import router as account_router
    from app.api.market_routes import router as market_router
    from app.api.position_routes import router as position_router
    from app.api.trading_routes import router as trading_router
    from app.api.strategy_routes import router as strategy_router
    from app.api.risk_routes import router as risk_router
    from app.api.log_routes import router as log_router
    from app.websocket.ws_handler import router as ws_router

    app.include_router(health_router, prefix="/api")
    app.include_router(mt5_router, prefix="/api/mt5")
    app.include_router(account_router, prefix="/api")
    app.include_router(market_router, prefix="/api/market")
    app.include_router(position_router, prefix="/api")
    app.include_router(trading_router, prefix="/api/trading")
    app.include_router(strategy_router, prefix="/api/strategy")
    app.include_router(risk_router, prefix="/api/risk")
    app.include_router(log_router, prefix="/api")
    app.include_router(ws_router)

    return app


app = create_app()
