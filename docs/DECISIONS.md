# Architecture Decision Records (ADR)

This log records every non-obvious engineering and architectural decision made during development.

---

## ADR-001: Native Windows Execution (No Docker for MT5 Engine)
- **Status:** Accepted
- **Context:** The MetaTrader5 Python official library relies on Windows IPC (Inter-Process Communication) to communicate directly with `terminal64.exe` running in the same desktop user session. It is completely incompatible with standard Linux Docker containers.
- **Decision:** The backend trading engine and MT5 adapter run natively on Windows. `docker-compose.yml` is reserved exclusively for optional auxiliary services like PostgreSQL.
- **Consequences:** Windows 10/11 or Windows Server (VPS) is strictly required for the MT5 trading backend.

---

## ADR-002: Single Uvicorn Worker Process
- **Status:** Accepted
- **Context:** The MetaTrader5 library maintains process-local state and does not support multi-process concurrent access to the same terminal instance. Running multiple uvicorn workers causes IPC race conditions, duplicate orders, and state corruption.
- **Decision:** Uvicorn is strictly configured to run with `workers=1`. Concurrency is managed via asyncio coroutines and a dedicated MT5 background worker thread with task queue.
- **Consequences:** High stability; zero IPC collision between workers.

---

## ADR-003: Single Choke Point for All Orders with Demo Gate
- **Status:** Accepted
- **Context:** Accidental live trading or orders bypassing risk limits could cause severe financial loss.
- **Decision:** Every order (market open, close, modify) MUST pass through `Mt5Gateway.send_order()`. Before sending any order to `mt5.order_send()`, the gateway queries account details and verifies `trade_mode == ACCOUNT_TRADE_MODE_DEMO`. If the account is `REAL` or `CONTEST`, the order is immediately rejected and an exception is raised.
- **Consequences:** Live trading is physically impossible in Version 1.

---

## ADR-004: Pure Deterministic Grid Engine with Injected Clock
- **Status:** Accepted
- **Context:** Testing grid trading logic with real time and MT5 calls produces flaky, non-deterministic tests.
- **Decision:** The strategy engine (`XAUUSDGridStrategy`) has zero MT5 imports and zero direct calls to `datetime.now()` or `time.monotonic()`. It relies on an injected `Clock` protocol and pure snapshot inputs (`MarketSnapshot`, `PortfolioSnapshot`). It returns immutable `OrderIntent` objects.
- **Consequences:** 100% deterministic unit testing and backtesting capability with instantaneous test execution.

---

## ADR-005: Position Sizing Uses Decimal with Strict Downward Rounding
- **Status:** Accepted
- **Context:** Standard IEEE 754 floating-point arithmetic introduces rounding artifacts (e.g. `0.01 * 3 = 0.030000000000000004`). If volume rounds up past the broker's step or maximum, the broker rejects the trade.
- **Decision:** All lot sizing arithmetic uses Python `Decimal` and `ROUND_DOWN`. Sizing clamps strictly between broker `volume_min` and `volume_max`, aligned to `volume_step`.
- **Consequences:** Guaranteed alignment with broker specifications; no floating-point volume rejections.

---

## ADR-006: State Machine Thread Safety via `threading.RLock`
- **Status:** Accepted
- **Context:** The state machine (`SystemState`) coordinates transitions across HTTP handlers, WebSocket broadcasts, and trading engine events. In nested property calls (e.g., `to_dict()` calling `self.display_state`), standard `Lock` causes a deadlock.
- **Decision:** Use `threading.RLock` (reentrant lock) to allow safe nested inspections within the same thread while preventing races across different threads.
- **Consequences:** Deadlock-free state management and thread-safe notifications.

---

## ADR-007: Two-Step Start with Typed Confirmation
- **Status:** Accepted
- **Context:** Accidental activation of automated trading can occur from accidental clicks.
- **Decision:** Starting the bot requires two steps: first requesting a nonce (`POST /api/trading/start-request`), and then confirming (`POST /api/trading/start`) with the exact typed string `"START DEMO"`.
- **Consequences:** Prevents accidental startup; guarantees explicit user intention.

---

## ADR-008: Instance Locking via PID Lockfile
- **Status:** Accepted
- **Context:** Running two bot processes concurrently against the same MT5 account causes duplicate trades and basket tracking errors.
- **Decision:** At startup, `main.py` writes its PID to `mt5terminal.lock`. If another active process owns the lockfile, the backend refuses to start and exits with an explanatory message.
- **Consequences:** Prevents duplicate running instances.
