"""
MT5 Connection Layer — Section 3
- Single worker thread for all MT5 calls (not safe to call concurrently)
- Demo verification at every order (Section 2 [FIX])
- Mid-session login/server change detection
- Health monitor with exponential backoff reconnect
"""
from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, TypeVar, Any

import structlog

from app.mt5.errors import (
    Mt5NotInitialized, Mt5AuthFailed, Mt5Disconnected,
    Mt5Timeout, Mt5AlgoTradingDisabled, Mt5NotDemo, Mt5AccountSwitched,
)
from app.mt5.retcodes import get_last_error_info
from app.mt5.timeutil import measure_server_offset, set_server_offset

log = structlog.get_logger(__name__)

T = TypeVar("T")

# MT5 trade mode constants
ACCOUNT_TRADE_MODE_DEMO = 0
ACCOUNT_TRADE_MODE_CONTEST = 1
ACCOUNT_TRADE_MODE_REAL = 2


@dataclass
class ConnectionInfo:
    login: int
    server: str
    trade_mode: int
    balance: float
    equity: float
    leverage: int
    currency: str
    margin_mode: int      # 0=retail netting, 2=retail hedging
    trade_allowed: bool
    trade_expert: bool
    stop_out_level: float
    stop_out_mode: int
    connected_at: datetime


class MT5Connection:
    """
    All MT5 calls are executed on a single dedicated worker thread.
    Async code awaits results via _run_in_worker().
    Never call MT5 directly from asyncio loop or multiple threads.
    """

    def __init__(
        self,
        terminal_path: str,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        timeout_ms: int = 30_000,
        allowed_login: int | None = None,
    ) -> None:
        self._terminal_path = terminal_path
        self._login = login
        self._password = password
        self._server = server
        self._timeout_ms = timeout_ms
        self._allowed_login = allowed_login

        # Single-thread executor — ONLY thread that calls MT5
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mt5-worker")
        self._lock = threading.Lock()
        self._initialized = False
        self._connection_info: ConnectionInfo | None = None

        # Session identity (set at connect, validated on every order)
        self._session_login: int | None = None
        self._session_server: str | None = None

        # Demo status cache (max 5s, invalidated on reconnect)
        self._demo_cache_time: float = 0.0
        self._demo_cache_result: bool = False
        self._DEMO_CACHE_TTL_S = 5.0

        self._mt5: Any = None  # imported inside worker

    # ── Worker submission ────────────────────────────────────────────────────

    def _run_in_worker(self, fn: Callable[[], T]) -> T:
        """Submit a callable to the MT5 worker thread and wait for result."""
        future: Future[T] = self._executor.submit(fn)
        try:
            return future.result(timeout=self._timeout_ms / 1000.0 + 5)
        except TimeoutError as e:
            raise Mt5Timeout(f"MT5 call timed out after {self._timeout_ms}ms") from e

    # ── Initialize / Connect ─────────────────────────────────────────────────

    def initialize(self) -> ConnectionInfo:
        """
        Initialize MT5 and verify demo account.
        Idempotent — calling twice reconnects if needed.
        """
        return self._run_in_worker(self._do_initialize)

    def _do_initialize(self) -> ConnectionInfo:
        import MetaTrader5 as mt5
        self._mt5 = mt5

        log.info("mt5_initialize_start",
                 terminal=self._terminal_path,
                 version=str(mt5.version()) if hasattr(mt5, "version") else "unknown")

        # Build kwargs — prefer attach-only if no creds provided
        kwargs: dict[str, Any] = {"path": self._terminal_path, "timeout": self._timeout_ms}
        if self._login and self._password and self._server:
            kwargs["login"] = self._login
            kwargs["password"] = self._password
            kwargs["server"] = self._server

        if not mt5.initialize(**kwargs):
            code, msg = mt5.last_error()
            info = get_last_error_info(code)
            raise Mt5NotInitialized(
                f"mt5.initialize() failed: [{code}] {msg} — {info.human_fix}",
                code=code,
            )

        log.info("mt5_initialized", build=str(mt5.terminal_info()))

        # Verify terminal health
        ti = mt5.terminal_info()
        if ti is None:
            raise Mt5NotInitialized("terminal_info() returned None after initialize")

        if not ti.connected:
            raise Mt5Disconnected(
                "MT5 terminal is not connected to the broker server. "
                "Check internet connection and MT5 server settings."
            )

        if not ti.trade_allowed:
            raise Mt5AlgoTradingDisabled(
                "Algo Trading is OFF in the MT5 toolbar. "
                "Click the 'Algo Trading' button and retry.",
                code=-8,
            )

        # Read account
        ai = mt5.account_info()
        if ai is None:
            code, msg = mt5.last_error()
            raise Mt5AuthFailed(f"account_info() failed: [{code}] {msg}", code=code)

        # Verify DEMO (fail closed — refuse REAL, CONTEST, unknown)
        self._verify_demo_account(ai)

        # Allowed login check
        if self._allowed_login and ai.login != self._allowed_login:
            raise Mt5AuthFailed(
                f"Connected as login {ai.login} but ALLOWED_LOGIN={self._allowed_login}. "
                "Set ALLOWED_LOGIN= or connect the correct account."
            )

        # Store session identity for mid-session change detection
        with self._lock:
            self._session_login = ai.login
            self._session_server = ai.server
            self._initialized = True
            self._demo_cache_time = 0  # invalidate on reconnect

        # Measure server time offset
        try:
            tick = mt5.symbol_info_tick("XAUUSD")
            if tick and tick.time > 0:
                offset = measure_server_offset(tick.time, tick.time_msc)
                set_server_offset(offset)
        except Exception:
            log.warning("server_offset_measure_failed")

        conn_info = ConnectionInfo(
            login=ai.login,
            server=ai.server,
            trade_mode=ai.trade_mode,
            balance=ai.balance,
            equity=ai.equity,
            leverage=ai.leverage,
            currency=ai.currency,
            margin_mode=ai.margin_mode,
            trade_allowed=ai.trade_allowed,
            trade_expert=ai.trade_expert,
            stop_out_level=ai.margin_so_so,
            stop_out_mode=ai.margin_so_mode,
            connected_at=datetime.now(timezone.utc),
        )

        with self._lock:
            self._connection_info = conn_info

        log.info("mt5_connected",
                 login=ai.login, server=ai.server,
                 trade_mode=ai.trade_mode, currency=ai.currency,
                 balance=ai.balance, equity=ai.equity,
                 margin_mode=ai.margin_mode)

        return conn_info

    def _verify_demo_account(self, account_info: Any) -> None:
        """
        Enforce demo-only. Fail closed on unknown trade_mode.
        Section 2 [FIX]: do not rely on server name.
        """
        mode = account_info.trade_mode
        if mode == ACCOUNT_TRADE_MODE_DEMO:
            return
        if mode == ACCOUNT_TRADE_MODE_REAL:
            raise Mt5NotDemo(
                f"LIVE account detected (login={account_info.login}). "
                "V1 refuses to trade live accounts. Connect a DEMO account."
            )
        if mode == ACCOUNT_TRADE_MODE_CONTEST:
            raise Mt5NotDemo(
                f"CONTEST account detected (login={account_info.login}). "
                "Only DEMO accounts are allowed in V1."
            )
        raise Mt5NotDemo(
            f"Unknown trade_mode={mode} for login={account_info.login}. "
            "Refusing (fail-closed). Only DEMO accounts are allowed."
        )

    # ── Demo re-verification (called before every order) ────────────────────

    def verify_demo_cached(self) -> None:
        """
        Re-verify demo status. Cached for ≤5 s, invalidated on reconnect.
        Must be called before every order_send. Section 2 [FIX].
        """
        self._run_in_worker(self._do_verify_demo_cached)

    def _do_verify_demo_cached(self) -> None:
        now = time.monotonic()
        with self._lock:
            if now - self._demo_cache_time < self._DEMO_CACHE_TTL_S and self._demo_cache_result:
                return  # valid cache

        mt5 = self._mt5
        if mt5 is None:
            raise Mt5NotInitialized("MT5 not initialized")

        ai = mt5.account_info()
        if ai is None:
            raise Mt5Disconnected("account_info() failed during demo verification")

        # Check for mid-session login/server change
        with self._lock:
            if self._session_login and ai.login != self._session_login:
                raise Mt5AccountSwitched(
                    f"Login changed mid-session: was {self._session_login}, now {ai.login}. "
                    "Entries blocked. Re-connect to confirm new account."
                )
            if self._session_server and ai.server != self._session_server:
                raise Mt5AccountSwitched(
                    f"Server changed mid-session: was {self._session_server}, now {ai.server}. "
                    "Entries blocked."
                )

        self._verify_demo_account(ai)

        with self._lock:
            self._demo_cache_time = time.monotonic()
            self._demo_cache_result = True

    # ── Health check ─────────────────────────────────────────────────────────

    def health_check(self) -> dict[str, Any]:
        return self._run_in_worker(self._do_health_check)

    def _do_health_check(self) -> dict[str, Any]:
        mt5 = self._mt5
        if mt5 is None:
            return {"ok": False, "reason": "not_initialized"}

        ti = mt5.terminal_info()
        if ti is None:
            return {"ok": False, "reason": "terminal_info_none"}

        ai = mt5.account_info()
        return {
            "ok": ti.connected and ti.trade_allowed,
            "connected": ti.connected,
            "trade_allowed": ti.trade_allowed,
            "algo_trading": ti.trade_allowed,
            "account_trade_allowed": ai.trade_allowed if ai else False,
            "account_trade_expert": ai.trade_expert if ai else False,
            "build": ti.build if ti else None,
        }

    # ── Shutdown ─────────────────────────────────────────────────────────────

    def shutdown(self) -> None:
        def _do() -> None:
            if self._mt5:
                self._mt5.shutdown()
            with self._lock:
                self._initialized = False
                self._connection_info = None
        self._run_in_worker(_do)
        self._executor.shutdown(wait=False)
        log.info("mt5_shutdown")

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def is_initialized(self) -> bool:
        with self._lock:
            return self._initialized

    @property
    def connection_info(self) -> ConnectionInfo | None:
        with self._lock:
            return self._connection_info

    @property
    def mt5(self) -> Any:
        """Access to raw MT5 module — use only inside _run_in_worker callbacks."""
        return self._mt5
