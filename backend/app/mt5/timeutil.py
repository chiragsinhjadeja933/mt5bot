"""
MT5 Server-Time ↔ UTC Utilities — Section 46.
MT5 timestamps are "broker server time encoded as if UTC" — not real UTC.
Offset is detected at startup, verified periodically.
All internal times stored in real UTC.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from threading import Lock

import structlog

log = structlog.get_logger(__name__)

_lock = Lock()
_server_offset_seconds: float = 0.0   # server_time - real_utc
_offset_detected_at: float = 0.0      # monotonic time of last detection


def set_server_offset(offset_seconds: float) -> None:
    """Record the measured server UTC offset (seconds)."""
    global _server_offset_seconds, _offset_detected_at
    with _lock:
        old = _server_offset_seconds
        _server_offset_seconds = offset_seconds
        _offset_detected_at = time.monotonic()
    if abs(offset_seconds - old) > 60:
        log.warning(
            "server_time_offset_changed",
            old_offset_s=old,
            new_offset_s=offset_seconds,
        )
    else:
        log.info("server_time_offset_set", offset_seconds=offset_seconds)


def get_server_offset_seconds() -> float:
    with _lock:
        return _server_offset_seconds


def server_ts_to_utc(server_ts: int | float) -> datetime:
    """
    Convert an MT5 server timestamp (POSIX seconds or ms) to real UTC datetime.
    If the value looks like milliseconds (> 1e11), it's converted first.
    """
    ts = float(server_ts)
    if ts > 1e11:
        ts /= 1000.0
    with _lock:
        offset = _server_offset_seconds
    real_utc_ts = ts - offset
    return datetime.fromtimestamp(real_utc_ts, tz=timezone.utc)


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def server_now_estimate() -> datetime:
    """Estimated current server time (UTC-encoded) based on detected offset."""
    with _lock:
        offset = _server_offset_seconds
    return datetime.fromtimestamp(time.time() + offset, tz=timezone.utc)


def measure_server_offset(latest_tick_time: int, latest_tick_time_msc: int | None = None) -> float:
    """
    Estimate server offset by comparing the latest tick timestamp to local UTC.
    Returns offset in seconds (server_ts - real_utc).
    Call this at startup and periodically (e.g. every 30 min).
    """
    real_utc_now = time.time()
    if latest_tick_time_msc is not None:
        server_ts = latest_tick_time_msc / 1000.0
    else:
        server_ts = float(latest_tick_time)
    offset = server_ts - real_utc_now
    log.debug("measure_server_offset", server_ts=server_ts, real_utc=real_utc_now, offset_s=offset)
    return offset
