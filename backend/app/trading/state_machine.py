"""
Bot State Machine — Section 15 [FIX/ADD]
Three orthogonal machines: ConnectionState, BotState, ExecutionMode.
Explicit transition table. Persisted EMERGENCY_STOP.
"""
from __future__ import annotations

import threading
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

import structlog

log = structlog.get_logger(__name__)


class ConnectionState(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    ERROR = "ERROR"


class BotState(str, Enum):
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPING = "STOPPING"
    EMERGENCY_STOP = "EMERGENCY_STOP"


class ExecutionMode(str, Enum):
    DRY_RUN = "DRY_RUN"
    DEMO_EXECUTION = "DEMO_EXECUTION"


class OrderClass(str, Enum):
    ENTRY = "ENTRY"           # increases exposure
    REDUCE = "REDUCE"         # closes/reduces exposure
    EMERGENCY_CLOSE = "EMERGENCY_CLOSE"


# Transition table: (from_state, to_state) -> set of allowed triggers
_BOT_TRANSITIONS: dict[tuple[BotState, BotState], list[str]] = {
    (BotState.READY, BotState.RUNNING): ["user_start", "api_start"],
    (BotState.RUNNING, BotState.PAUSED): ["user_pause", "api_pause", "risk_limit"],
    (BotState.PAUSED, BotState.RUNNING): ["user_resume", "api_resume"],
    (BotState.RUNNING, BotState.STOPPING): ["user_stop", "api_stop"],
    (BotState.PAUSED, BotState.STOPPING): ["user_stop", "api_stop"],
    (BotState.STOPPING, BotState.READY): ["stopped"],
    (BotState.READY, BotState.EMERGENCY_STOP): ["emergency", "risk_emergency"],
    (BotState.RUNNING, BotState.EMERGENCY_STOP): ["emergency", "risk_emergency"],
    (BotState.PAUSED, BotState.EMERGENCY_STOP): ["emergency", "risk_emergency"],
    (BotState.STOPPING, BotState.EMERGENCY_STOP): ["emergency"],
    # Reset from EMERGENCY_STOP requires manual typed confirmation + reconciliation
    (BotState.EMERGENCY_STOP, BotState.READY): ["manual_reset_confirmed"],
    # ERROR always requires reconciliation before READY
    (BotState.READY, BotState.READY): ["reconciliation_ok"],  # no-op
}

# Composite display state (externally shown)
_DISPLAY_STATE_MAP: dict[tuple[ConnectionState, BotState], str] = {
    (ConnectionState.DISCONNECTED, BotState.READY): "DISCONNECTED",
    (ConnectionState.CONNECTING, BotState.READY): "CONNECTING",
    (ConnectionState.CONNECTED, BotState.READY): "READY",
    (ConnectionState.CONNECTED, BotState.RUNNING): "RUNNING",
    (ConnectionState.CONNECTED, BotState.PAUSED): "PAUSED",
    (ConnectionState.CONNECTED, BotState.STOPPING): "STOPPING",
    (ConnectionState.CONNECTED, BotState.EMERGENCY_STOP): "EMERGENCY_STOP",
    (ConnectionState.ERROR, BotState.READY): "ERROR",
}


def is_order_allowed(
    order_class: OrderClass,
    conn_state: ConnectionState,
    bot_state: BotState,
) -> bool:
    """
    Section 15 [FIX]: classify orders instead of blanket blocking.
    ENTRY blocked in PAUSED/EMERGENCY/ERROR/DISCONNECTED.
    REDUCE allowed in PAUSED/ERROR if MT5 reachable.
    EMERGENCY_CLOSE always attempted.
    """
    if order_class == OrderClass.EMERGENCY_CLOSE:
        # Always attempt (even in DISCONNECTED — will fail gracefully)
        return True

    if conn_state in (ConnectionState.DISCONNECTED, ConnectionState.CONNECTING):
        return False

    if order_class == OrderClass.ENTRY:
        return bot_state == BotState.RUNNING

    if order_class == OrderClass.REDUCE:
        return bot_state in (BotState.RUNNING, BotState.PAUSED) and \
               conn_state == ConnectionState.CONNECTED

    return False


@dataclass
class SystemState:
    connection_state: ConnectionState = ConnectionState.DISCONNECTED
    bot_state: BotState = BotState.READY
    execution_mode: ExecutionMode = ExecutionMode.DRY_RUN
    emergency_stop_persisted: bool = False
    last_transition_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_trigger: str = ""
    sequence_number: int = 0
    error_reason: str = ""

    _lock: threading.RLock = field(default_factory=threading.RLock, compare=False, repr=False)
    _listeners: list[Callable] = field(default_factory=list, compare=False, repr=False)

    def add_listener(self, fn: Callable) -> None:
        with self._lock:
            self._listeners.append(fn)

    def transition_connection(self, new_state: ConnectionState,
                               reason: str = "") -> None:
        with self._lock:
            old = self.connection_state
            self.connection_state = new_state
            self.sequence_number += 1
            self.last_transition_at = datetime.now(timezone.utc)
            self.last_trigger = reason
            if new_state == ConnectionState.ERROR:
                self.error_reason = reason
        log.info("connection_state_transition",
                 old=old, new=new_state, reason=reason, seq=self.sequence_number)
        self._notify()

    def transition_bot(self, new_state: BotState, trigger: str) -> None:
        with self._lock:
            old = self.bot_state
            key = (old, new_state)
            allowed_triggers = _BOT_TRANSITIONS.get(key, [])
            if trigger not in allowed_triggers and old != new_state:
                log.error("illegal_bot_state_transition",
                          old=old, new=new_state, trigger=trigger)
                raise ValueError(
                    f"Illegal bot state transition: {old} → {new_state} "
                    f"(trigger={trigger}). Allowed: {allowed_triggers}"
                )
            self.bot_state = new_state
            self.sequence_number += 1
            self.last_transition_at = datetime.now(timezone.utc)
            self.last_trigger = trigger
            if new_state == BotState.EMERGENCY_STOP:
                self.emergency_stop_persisted = True
        log.info("bot_state_transition",
                 old=old, new=new_state, trigger=trigger, seq=self.sequence_number)
        self._notify()

    def set_mode(self, mode: ExecutionMode) -> None:
        with self._lock:
            old = self.execution_mode
            self.execution_mode = mode
            self.sequence_number += 1
        log.info("execution_mode_changed", old=old, new=mode)
        self._notify()

    @property
    def display_state(self) -> str:
        with self._lock:
            key = (self.connection_state, self.bot_state)
        return _DISPLAY_STATE_MAP.get(key, f"{self.connection_state}/{self.bot_state}")

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "connection_state": self.connection_state,
                "bot_state": self.bot_state,
                "execution_mode": self.execution_mode,
                "display_state": self.display_state,
                "emergency_stop_persisted": self.emergency_stop_persisted,
                "sequence_number": self.sequence_number,
                "last_transition_at": self.last_transition_at.isoformat(),
                "last_trigger": self.last_trigger,
                "error_reason": self.error_reason,
            }

    def _notify(self) -> None:
        snapshot = self.to_dict()
        for fn in self._listeners:
            try:
                fn(snapshot)
            except Exception:
                pass
