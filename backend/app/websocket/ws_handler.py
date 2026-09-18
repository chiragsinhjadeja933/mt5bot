"""
WebSocket Handler — Section 25 [ADD]
Full snapshot on connect, then deltas with sequence numbers.
Heartbeat, throttling, backpressure.
Auth via token query param.
"""
from __future__ import annotations

import asyncio
import json
import secrets
import time
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.main import _system_state

log = structlog.get_logger(__name__)
router = APIRouter()

# Active WebSocket clients
_clients: list[WebSocket] = []
_broadcast_lock = asyncio.Lock()


async def _verify_ws_token(websocket: WebSocket) -> bool:
    token = websocket.query_params.get("token", "")
    expected = get_settings().api_token.get_secret_value()
    if not secrets.compare_digest(token, expected):
        await websocket.close(code=4001, reason="Unauthorized")
        return False
    return True


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()

    # Auth check
    if not await _verify_ws_token(websocket):
        return

    # Origin check
    origin = websocket.headers.get("origin", "")
    settings = get_settings()
    if origin and origin not in (settings.frontend_origin, ""):
        await websocket.close(code=4003, reason="Origin not allowed")
        return

    _clients.append(websocket)
    log.info("ws_client_connected", clients=len(_clients))

    try:
        # Send full snapshot immediately on connect
        snapshot = await _build_snapshot()
        await websocket.send_text(json.dumps({"type": "snapshot", **snapshot}))

        # Heartbeat loop
        while True:
            try:
                # Wait for ping or timeout
                try:
                    msg = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                    # Echo pings
                    if msg == "ping":
                        await websocket.send_text(json.dumps({"type": "pong",
                                                              "ts": datetime.now(timezone.utc).isoformat()}))
                except asyncio.TimeoutError:
                    # Send heartbeat
                    await websocket.send_text(json.dumps({
                        "type": "heartbeat",
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "state": _system_state.to_dict(),
                    }))
            except WebSocketDisconnect:
                break

    except Exception as e:
        log.warning("ws_error", error=str(e))
    finally:
        if websocket in _clients:
            _clients.remove(websocket)
        log.info("ws_client_disconnected", clients=len(_clients))


async def _build_snapshot() -> dict:
    """Build full state snapshot for new clients."""
    from app.api.mt5_routes import _gateway

    snapshot: dict = {
        "sequence": _system_state.sequence_number,
        "state": _system_state.to_dict(),
        "account": None,
        "tick": None,
        "positions": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if _gateway:
        try:
            account = _gateway.get_account()
            snapshot["account"] = account.to_dict()
        except Exception:
            pass

        try:
            settings = get_settings()
            tick = _gateway.get_tick(settings.gold_symbol)
            snapshot["tick"] = tick.to_dict()
        except Exception:
            pass

        try:
            positions = _gateway.get_positions()
            snapshot["positions"] = [p.to_dict() for p in positions]
        except Exception:
            pass

    return snapshot


async def broadcast(message: dict) -> None:
    """Broadcast a message to all connected clients. Drop stale frames."""
    if not _clients:
        return

    text = json.dumps(message, default=str)
    dead = []
    for client in _clients[:]:
        try:
            await asyncio.wait_for(client.send_text(text), timeout=2.0)
        except Exception:
            dead.append(client)

    for c in dead:
        if c in _clients:
            _clients.remove(c)


async def market_data_broadcaster(symbol: str, interval_s: float = 0.25) -> None:
    """
    Background task: poll market data and broadcast to all WS clients.
    Price ≤ 4 msgs/s (250ms interval). Section 25 [ADD] throttling.
    """
    from app.api.mt5_routes import _gateway
    last_broadcast = 0.0

    while True:
        await asyncio.sleep(interval_s)
        try:
            gw = _gateway
            if gw is None:
                continue

            now = time.monotonic()
            if now - last_broadcast < interval_s:
                continue

            tick = gw.get_tick(symbol)
            account = gw.get_account()
            positions = gw.get_positions()

            await broadcast({
                "type": "market_update",
                "sequence": _system_state.sequence_number,
                "tick": tick.to_dict() if tick else None,
                "account": account.to_dict() if account else None,
                "positions": [p.to_dict() for p in positions],
                "state": _system_state.to_dict(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            last_broadcast = now

        except Exception as e:
            log.debug("market_broadcast_error", error=str(e))


_broadcaster_task: asyncio.Task | None = None


def start_broadcaster(symbol: str) -> None:
    global _broadcaster_task
    if _broadcaster_task is None or _broadcaster_task.done():
        try:
            loop = asyncio.get_running_loop()
            _broadcaster_task = loop.create_task(market_data_broadcaster(symbol))
            log.info("market_broadcaster_started", symbol=symbol)
        except RuntimeError:
            pass

