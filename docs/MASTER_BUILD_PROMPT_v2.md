# MASTER BUILD PROMPT — v2 (EDITED)

## MT5 Demo Trading Terminal + Automated XAUUSD Trading Bot

> **HOW TO READ THIS EDIT**
> - Original text is preserved. Nothing was removed.
> - **[FIX]** = something in the original was wrong, contradictory, impossible, or unsafe, and is now corrected.
> - **[ADD]** = something that was missing and is required for this type of project.
> - Untagged text = original, unchanged.
> - Original section numbers 1–44 are kept so cross-references still work. New cross-cutting sections are numbered 45–52 at the end. A new **Section 0** comes first.

---

## 0. AGENT OPERATING RULES, PLATFORM REALITY, PRE-FLIGHT **[ADD]**

### 0.1 How you (the coding agent) must work

1. Work in **phases with gates** (Section 36). At the end of every phase, stop and output a **PHASE REPORT** (template in Section 52). Do not start the next phase until the user approves.
2. **Never claim something works without pasting the actual command output/test result that proves it.** "Should work" is not acceptable.
3. If the environment cannot run something (no MT5, no Windows, no demo account), **say so explicitly and stop that part**. Do not mock it to make it look finished.
4. **Never ask the user to paste credentials into chat.** The user puts them in a local `.env` file. If a credential is ever pasted into chat, tell the user to change that password.
5. Keep `docs/PROGRESS.md` (checklist mirroring Section 42) and `docs/DECISIONS.md` (short ADR-style log of every non-obvious decision and why).
6. Prefer boring, explicit, testable code over clever code. This system controls money-like state; correctness beats features.
7. When the spec is ambiguous or two requirements conflict, **choose the safer behavior, record it in DECISIONS.md, and flag it in the phase report.**

### 0.2 Platform reality **[FIX]**

The original prompt implied Docker + Linux-style deployment. That cannot work:

- The official `MetaTrader5` Python package **only works on Windows** and only talks to a **desktop MT5 terminal (terminal64.exe) running on the same machine**, under the same OS user session.
- It is **not** usable inside a Linux Docker container. Wine/third-party bridges are **out of scope for V1**.
- **Therefore:** the backend runs **natively on Windows** (local PC, Windows VM, or Windows VPS).
- `docker-compose.yml` is limited to optional supporting services (PostgreSQL, optionally a static frontend server). The MT5 adapter never runs in Docker.
- Check that a `MetaTrader5` wheel exists for the installed Python version (`pip index versions MetaTrader5` / `pip install`); if not, pick a supported Python version and record it in DECISIONS.md.
- Run **one** uvicorn worker only (MT5 state is process-local). No multi-worker, no autoscaling.

### 0.3 Decisions/facts to confirm with the user before Phase 3 **[ADD]**

- Operating system and whether MT5 terminal is installed and logged in to a **demo** account
- Broker/server name, **account currency** (do not assume USD), leverage
- **Account margin mode: HEDGING vs NETTING** (see Section 47 — a grid strategy needs hedging)
- Exact gold symbol name at this broker (`XAUUSD`, `XAUUSDm`, `XAUUSD.a`, `GOLD`, …)
- Contract size, lot min/max/step, digits, stops level, filling modes (read from MT5, never hardcode)
- Broker server timezone offset
- Where the bot will run (PC vs VPS) and whether the PC/internet can be assumed always-on

### 0.4 Honesty rules **[ADD]**

- This is a software-engineering task, not a profit promise. Demo results do not predict live results (demo fills have no realistic slippage/liquidity limits).
- Never state or imply that any configured strategy is profitable.
- Grid/averaging-down/multiplier strategies can lose an entire account through a single sustained move. The UI, README, and RISK_MANAGEMENT.md must say this plainly.

---

## 1. CORE OBJECTIVE

**MT5 Demo Trading Terminal + Automated XAUUSD Trading Bot**

You are a senior quantitative software engineer, Python backend engineer, MT5/MQL5 developer, and trading-system architect.

Build a complete, production-quality trading terminal for MetaTrader 5 demo accounts, with a custom dashboard/control panel and an automated XAUUSD trading engine.

The system must initially operate DEMO ONLY. Do not implement live-account trading in Version 1.

The goal is to create a system similar in functionality to the trading activity shown in the provided reference video: multiple XAUUSD positions, automated entries, position management, basket profit tracking, real-time P/L, and centralized controls.

Do NOT assume that the strategy shown in the video is profitable. The system must accurately execute and report whatever strategy is configured.

Create this architecture:

```
                    CUSTOM TRADING TERMINAL
                             │
                             ▼
                    ┌─────────────────┐
                    │   WEB/GUI UI    │
                    │                 │
                    │ Account         │
                    │ Market Data     │
                    │ Positions       │
                    │ Orders          │
                    │ P/L             │
                    │ Strategy        │
                    │ Risk Controls   │
                    │ Logs            │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ TRADING ENGINE  │
                    │                 │
                    │ Signal Engine   │
                    │ Grid Engine     │
                    │ Position Mgmt   │
                    │ TP/SL Manager   │
                    │ Risk Manager    │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ MT5 ADAPTER     │
                    │                 │
                    │ Connection      │
                    │ Market Data     │
                    │ Orders          │
                    │ Positions       │
                    │ History         │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ MT5 TERMINAL    │
                    │ DEMO ACCOUNT    │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ BROKER DEMO     │
                    │ TRADE SERVER    │
                    └─────────────────┘
```

The MT5 demo account must remain the source of truth for:

- account balance
- equity
- margin
- free margin
- positions
- orders
- executions
- realized P/L
- floating P/L
- trading errors

The custom terminal must NOT fabricate trading results.

**[ADD] Data provenance rule.** Every number shown in the UI/API carries a provenance tag: `MT5` (read directly), `DERIVED` (computed from MT5 data, formula documented), or `THEORETICAL` (dry-run/backtest only). `THEORETICAL` values are never shown in the same widget as, or summed with, `MT5` values, and are always visually labeled.

**[ADD] Process model.** One backend process containing: MT5 worker thread, market-data service, trading engine loop, risk manager loop, reconciliation loop, API/WebSocket. Communication between them via an internal event bus/queues, not shared mutable globals (see Section 45).

---

## 2. IMPORTANT DEMO-ONLY REQUIREMENT

Version 1 must have a hard DEMO-ONLY safety mechanism.

The system must:

- detect the connected MT5 account
- detect whether the account is demo
- display account type prominently
- refuse to start automated trading if the account is not confirmed as DEMO
- provide a global "DEMO_ONLY=true" configuration
- require explicit confirmation before starting the bot
- have an emergency stop
- have a "CLOSE ALL POSITIONS" button
- have a "PAUSE BOT" button

Never silently switch to a live account.

Do not request or expose credentials in source code.

Use environment variables or secure local configuration.

**[FIX] A config flag alone is not a safety mechanism.** `DEMO_ONLY=true` is trivially editable. Enforce demo-only in code, at the single choke point:

1. Detect account type from `mt5.account_info().trade_mode`: `ACCOUNT_TRADE_MODE_DEMO` = OK. `ACCOUNT_TRADE_MODE_CONTEST` and `ACCOUNT_TRADE_MODE_REAL` = **refuse**. Any unknown value = **refuse (fail closed)**. Do not rely on the server name containing the word "Demo".
2. The **`MT5Gateway.send_order()` function is the only function in the codebase allowed to call `mt5.order_send`**, and it **re-verifies demo status immediately before every order** (cached ≤ 5 seconds, invalidated on any reconnect). If verification fails or cannot be performed → order refused, state → `ERROR`, alert raised.
3. Detect **login/server change mid-session** (user switches account in the terminal). If `account_info().login/server` differs from the one confirmed at connect time → treat as `ERROR`, block all entry orders, require manual re-confirmation.
4. In V1, `DEMO_ONLY=false` is **rejected by config validation** (startup fails with a clear message). There must be **no code path** that trades a non-demo account.
5. Optional `ALLOWED_LOGIN` env var: if set, refuse any other login.
6. "Explicit confirmation before starting the bot" = a modal showing account login, server, `DEMO`, strategy name, mode (DRY/DEMO EXEC), max exposure summary, and requiring the user to **type** `START DEMO`. The backend verifies the confirmation token server-side (a UI-only check is not enough).
7. Emergency stop, close-all, and pause must work **even in states where entries are blocked**, and must never be gated behind confirmation dialogs that slow them down (single click + one confirm at most).

---

## 3. MT5 CONNECTION

Use the official MetaTrader 5 Python integration where appropriate.

The system must support:

```
MT5 terminal
    ↓
logged-in demo account
    ↓
Python MT5 adapter
```

The connection layer must support:

- initialize MT5
- login
- server detection
- account information
- connection health
- terminal information
- symbol information
- tick data
- positions
- orders
- trade history
- order submission
- order modification
- position closing
- shutdown/reconnect

Implement a dedicated module:

```
backend/
    mt5/
        connection.py
        market_data.py
        orders.py
        positions.py
        history.py
        account.py
        reconciliation.py
        gateway.py        # [ADD] the ONLY place order_send/order_check are called
        symbols.py        # [ADD] symbol resolution + broker constraints
        errors.py         # [ADD] MT5 last_error + retcode -> structured exceptions
        retcodes.py       # [ADD] retcode table (Section 49)
        timeutil.py       # [ADD] server-time <-> UTC (Section 46)
```

Do not scatter MT5 API calls throughout the application.

All MT5 interaction must go through a clean adapter/service layer.

**[ADD] Adapter requirements**

- **MT5 API is synchronous and not safe to call concurrently.** All MT5 calls execute on **one dedicated worker thread** (single-thread executor) guarded by a lock. Async code awaits results via `run_in_executor`/queue. Never call MT5 directly from the asyncio event loop or from multiple threads.
- Every MT5 call goes through a wrapper that: checks for `None`/failure returns, captures `mt5.last_error()`, applies a timeout budget, logs latency, and raises a **structured exception** (`Mt5NotInitialized`, `Mt5AuthFailed`, `Mt5Disconnected`, `Mt5OrderRejected`, `Mt5Timeout`, …).
- Define a **`TradingGateway` interface** (abstract): `get_account()`, `get_tick()`, `get_positions()`, `send_order()`, `close_position()`, `modify_position()`, `get_deals()`. Implementations: `Mt5Gateway` (real), `DryRunGateway` (Section 31), later `BacktestGateway` (Section 32). Test fakes live in `tests/` only.
- **Health monitor:** `terminal_info().connected`, `terminal_info().trade_allowed` (algo trading enabled in terminal), `account_info().trade_allowed`, `account_info().trade_expert`, last-tick age, call error rate. Reconnect with exponential backoff + jitter; state machine reflects the result (Section 15).
- On (re)connect: re-verify demo status, login/server, symbol availability, margin mode.
- Log `mt5.version()`, terminal build, and package version at startup.
- Missing prerequisites that must be detected and reported clearly (not silently failing): terminal not running, "Algo Trading" button disabled, "Allow algorithmic trading" not enabled in terminal options, wrong terminal path, wrong login/server, investor (read-only) password used for login.

---

## 4. ACCOUNT CONNECTION FLOW

The user should be able to configure:

- MT5 Terminal Path
- Login
- Server
- Password

But credentials must NEVER be hardcoded.

Use something like:

```
MT5_LOGIN=
MT5_PASSWORD=
MT5_SERVER=
MT5_TERMINAL_PATH=
```

Provide:

```
[ CONNECT MT5 ]
```

After connection, display:

```
Connection: CONNECTED
Account: XXXXXXXX
Server: Broker-Demo
Account Type: DEMO
Balance: $10,000
Equity: $10,000
Leverage: 1:500
```

If connection fails, show the actual MT5 error code and a human-readable explanation.

Do not claim successful connection unless MT5 actually confirms it.

**[ADD] Details**

- **Credentials are optional if the terminal is already logged in.** `mt5.initialize(path=...)` without login attaches to the terminal's current account — this avoids handling a password at all and is the **preferred** mode. Use `MT5_LOGIN/PASSWORD/SERVER` only when explicitly needed. Load secrets with `pydantic.SecretStr`; never log or return them.
- Display **account currency** rather than a hardcoded "$" (the example above is illustrative).
- Also display: margin mode (HEDGING/NETTING), stop-out level and mode, algo-trading status (terminal + account), server timezone offset, symbol resolved for gold, and **any blocking condition** with a plain-English fix (e.g. "Algo Trading is OFF in the MT5 toolbar — click it and retry").
- Common error mapping is required (see Section 49), e.g. `-6` authorization failed, `-8` auto-trading disabled, `-10003` IPC initialize failed, `-10004` no connection.
- `CONNECT` is idempotent: pressing it twice must not create two sessions.

---

## 5. FIRST TEST — MUST WORK BEFORE STRATEGY

Before implementing the aggressive trading strategy, create a connection test mode.

The test sequence:

```
CONNECT
   ↓
READ ACCOUNT
   ↓
READ XAUUSD
   ↓
READ BID/ASK
   ↓
READ SPREAD
   ↓
PLACE 0.01 LOT DEMO TRADE
   ↓
VERIFY POSITION EXISTS
   ↓
DISPLAY FLOATING P/L
   ↓
CLOSE POSITION
   ↓
VERIFY POSITION CLOSED
   ↓
VERIFY TRADE HISTORY
```

Create a button:

```
[ RUN MT5 CONNECTION TEST ]
```

The test must fail safely if any stage fails.

Do not proceed to automated strategy execution until this test works correctly.

**[ADD] Test details**

- **Pre-checks before placing anything:** demo confirmed; algo trading enabled; symbol resolved, selected in Market Watch (`symbol_select`), `trade_mode == FULL`; **market open** (fresh tick, session active); volume ≥ `volume_min` (use `volume_min` if it is > 0.01); spread ≤ configured max; margin sufficient via `order_calc_margin`. Any failure → test stops **before** trading with a specific reason.
- Run `order_check` before `order_send`; show its result.
- Use a distinct **TEST magic number** and comment (`"mt5term-test"`), so test trades are never confused with strategy trades.
- **Cleanup guarantee:** if any stage after opening fails, a `finally` path attempts to close the test position (retry with backoff) and reports whether cleanup succeeded. The test must never leave an orphan position silently.
- History verification: `history_deals_get` by position id; expect an entry deal and exit deal; **retry for a few seconds** because history can lag; compare profit/commission/swap with what was displayed.
- Record per-stage pass/fail, retcodes, latency (ms), and slippage (requested vs filled) in `connection_tests` table (Section 24) and show it in the UI.
- **Gate:** store `connection_test_passed_at` with login+server. Starting **DEMO EXECUTION** mode requires a passing test for the *same* login/server within a configurable window (default 24 h). DRY RUN does not require it.
- A confirmation dialog is required before the test trades ("This will open and close a real position on demo account XXXX").

---

## 6. CUSTOM TERMINAL UI

Build a professional trading terminal.

Preferred stack:

**Frontend**

- React
- Vite
- TypeScript
- Tailwind CSS
- Recharts or another suitable charting library
- WebSocket for real-time updates

**Backend**

- Python
- FastAPI
- WebSocket
- asyncio where appropriate
- official MetaTrader5 Python package

**Database**

Use PostgreSQL if practical.

SQLite may be used for the initial local prototype.

Store:

- bot configurations
- strategy configurations
- orders
- positions
- executions
- P/L snapshots
- events
- errors
- system state
- risk events

**[FIX/ADD] Stack notes**

- Recharts is fine for P/L/equity curves but is **poor for live candlestick charts**. Use **TradingView `lightweight-charts`** (open source) for the XAUUSD price chart; Recharts (or the same library) for equity/P/L.
- Frontend state: TanStack Query for REST, a small store (Zustand) for WebSocket-driven live state. Strict TypeScript, no `any`.
- Backend: SQLAlchemy 2.x + Alembic; Pydantic v2 for schemas/config; `structlog` or stdlib JSON logging.
- Money columns as `NUMERIC`/Decimal (not float) in PostgreSQL; in SQLite store as string/integer-minor-units with a documented conversion. Schema must be portable between SQLite and PostgreSQL. All timestamps stored in **UTC**.
- Backend and frontend bind to **localhost** by default (Section 34).

---

## 7. DASHBOARD

Create the following sections.

**ACCOUNT**

Display:

- Balance
- Equity
- Floating P/L
- Realized P/L
- Free Margin
- Used Margin
- Margin Level
- Leverage
- Account Type
- Server
- Connection Status

**[ADD]** Also: account currency, stop-out level and "distance to stop-out" (equity buffer), margin mode, algo-trading status, data age.

---

**MARKET**

For XAUUSD:

- Bid
- Ask
- Spread
- Last Price
- Tick Time
- Daily High
- Daily Low

Show a live price chart.

**[ADD]** Also: resolved broker symbol name, session status (OPEN/CLOSED), tick age in ms with a **STALE** badge when over threshold, spread vs configured max. Note: many gold CFDs report `last = 0`; show mid price instead of a misleading zero.

---

**POSITIONS**

Table:

- Ticket
- Symbol
- Direction
- Volume
- Entry Price
- Current Price
- SL
- TP
- Floating P/L
- Swap
- Open Time
- Magic Number
- Strategy

Buttons:

- Close
- Modify SL
- Modify TP

**[ADD]** Extra columns: commission (from deals), comment, basket id, **scope badge (BOT / MANUAL / FOREIGN)**. Actions on non-bot positions are disabled by default and require an explicit per-action confirmation. Modify actions validate against `stops_level`/`freeze_level` before sending and show the broker's retcode on failure. Provide a "Close selected" and per-basket close.

---

## 8. ORDERS / HISTORY

Create trade history:

- Ticket
- Order Type
- Symbol
- Volume
- Entry
- Exit
- Profit
- Commission
- Swap
- Open Time
- Close Time
- Strategy
- Reason

Allow filtering by:

- date
- symbol
- BUY/SELL
- profitable/loss
- strategy

**[ADD]**

- "Reason" for close comes from MT5's `DEAL_REASON` (SL, TP, stop-out, client, expert, mobile, web) plus the bot's own reason (basket TP, basket SL, risk, kill switch, manual).
- Show position id, entry deal ticket, exit deal ticket; net profit = profit + commission + swap (+ fee).
- Pagination/virtualized table, sort, CSV export. Timezone toggle (UTC / server / local). Pending orders shown separately from history.

---

## 9. STRATEGY CONTROL PANEL

Create:

```
Strategy Status: ON/OFF

Strategy:
[ Grid ]
[ Trend ]
[ Breakout ]
[ Scalping ]
[ Custom ]
```

For Version 1, implement a configurable XAUUSD grid/basket engine.

Do not hardcode the video behavior as fact.

All strategy parameters must be configurable.

**[FIX]** Trend/Breakout/Scalping/Custom are **not implemented in V1**. Show them as disabled with "Not implemented in V1" — do not create clickable placeholders that do nothing (this would violate Section 43). The strategy plugin interface (Section 32) must make adding them later possible without changing the engine.

**[ADD]** Panel shows: mode (DRY RUN / DEMO EXECUTION), loaded config version/hash, validation result, **worst-case exposure preview** (Section 10), start/pause/stop controls, current basket summary, last signal, last risk verdict, and why the bot is not trading (e.g. "cooldown 23s", "spread too wide", "risk limit: daily loss").

---

## 10. GRID STRATEGY

Implement configurable parameters:

- Symbol = XAUUSD
- Initial Lot = 0.01
- Maximum Positions = 20
- Grid Distance = configurable points
- Lot Multiplier = configurable
- Maximum Lot = configurable
- Basket Take Profit = configurable
- Basket Stop Loss = configurable
- Maximum Drawdown = configurable
- Maximum Margin Usage = configurable
- Cooldown Between Entries = configurable

Trading Direction:

- BUY
- SELL
- BOTH

Example:

```
SELL
 ↓
Price moves according to grid condition
 ↓
SELL additional position
 ↓
Continue until:
    maximum positions
    basket TP
    basket SL
    risk limit
```

Do NOT automatically use martingale.

Provide:

Lot progression:

- [ Fixed ]
- [ Multiplier ]
- [ Custom ]

Example fixed:

```
0.01
0.01
0.01
0.01
```

Example multiplier:

```
0.01
0.015
0.0225
0.0337
```

The system must enforce a maximum lot size.

**[FIX] Corrections and precision**

1. **"Points" must be defined.** `grid_distance_points` is in MT5 *points* (`symbol_info.point`). On a 2-digit gold symbol, 1 point = 0.01 price units, so 100 points = 1.00 price units. Read `point`/`digits` from the broker; show the distance in points, price units, and account-currency-per-0.01-lot. Provide a `grid_distance` unit selector or clearly label units everywhere.
2. **The multiplier example is not executable as written.** 0.015, 0.0225, 0.0337 violate a 0.01 lot step. Volumes are always **rounded (down) to the broker's `volume_step`**, clamped to `volume_min`/`volume_max`/`max_lot`. The UI shows **requested vs effective** lot for each level (e.g. 0.01, 0.01, 0.02, 0.03). If two levels collapse to the same lot because of rounding, show that.
3. **Martingale contradiction resolved:** "Do NOT automatically use martingale" means: the default is `lot_mode = "fixed"`, `lot_multiplier = 1.0`. Any multiplier > 1.0 requires `allow_multiplier: true` **and** passes the worst-case exposure check below, and is displayed with an "AVERAGING / MARTINGALE-LIKE — HIGH RISK" warning. Aggressive Demo Mode (Section 21) may enable it, still within all hard caps.
4. **"Price moves according to grid condition" was undefined.** Make it explicit and configurable:
   - `grid_mode`: `"adverse"` (add when price moves *against* the basket by `grid_distance` — averaging down) or `"favorable"` (add when price moves *in favor* — pyramiding). **No silent default: the config must state it** (validation fails if missing).
   - `grid_anchor`: `"last_entry"` or `"average_entry"`.
   - `first_entry`: `"manual_trigger"` | `"immediate_on_start"` | `"signal"` (signal = a configurable condition; V1 ships with a simple documented one, no claimed edge).
   - For SELL, "adverse" = price rises; for BUY, price falls. Use **bid for SELL/ask for BUY reference logic as appropriate** and document which price triggers each rule.
5. **Direction BOTH** = two **independent baskets** (BUY basket, SELL basket), each with its own id, magic number, TP/SL, and risk accounting. This **requires a hedging account** (Section 47). On a netting account, BOTH is refused and single-direction grid is allowed only with a warning.
6. Add: `max_total_lots` (sum cap), `min_grid_distance` sanity vs spread (e.g. distance ≥ N × current spread), optional `grid_step_scaling`, `rearm_after_basket_close` (bool) + `rearm_delay_seconds`, `allowed_sessions`, `max_entries_per_hour` (mirrors Risk Manager).
7. **Worst-case exposure preview (required before start):** given the config and current symbol specs, compute and display: total lots at max positions, total margin required (`order_calc_margin`), price level at which margin level hits stop-out, and floating loss at +X/-X adverse move (X configurable, default e.g. 1%, 3%, 5%). **Block start** if any figure violates the Risk Manager limits.
8. The strategy emits **order intents**; it never calls MT5. The engine decides and executes via Risk Manager → Gateway (Section 19).

---

## 11. BASKET MANAGEMENT

Treat multiple positions belonging to the same strategy as a basket.

Calculate:

- Total Volume
- Weighted Average Entry
- Current Basket P/L
- Basket P/L %
- Number of Positions
- Margin Used
- Distance to TP
- Distance to SL

Example:

```
XAUUSD SELL BASKET

Positions: 8
Total Lots: 0.84
Average Entry: 3640.25
Current Price: 3635.80

Floating P/L: +$142.35

Basket TP: +$150
Basket SL: -$100
```

When basket TP is reached:

```
CLOSE ALL BASKET POSITIONS
```

Verify every position was actually closed.

Do not assume that an order succeeded just because a request was sent.

**[FIX] Example corrected.** The example's numbers are internally inconsistent: with a typical 100 oz contract, 0.84 lots × 4.45 price move ≈ **$373.80**, not $142.35. The example is now **format-only**; all real values come from MT5 (`position.profit`, `swap`, commissions from deals) and never from `entry − price` arithmetic (Section 39). A unit test must assert the corrected arithmetic using the symbol's real `trade_contract_size`/`tick_value`.

**[ADD] Basket rules**

- **Membership:** a position belongs to a basket by `magic` + a basket id encoded in `comment` and persisted in the DB. Reconstructable from MT5 alone after a restart (Section 16).
- **Weighted average entry** = Σ(volume × price_open) / Σ(volume). Distance to TP/SL shown in **currency and points**.
- **Current price for closing math:** BUY baskets close at **bid**, SELL baskets close at **ask**. Use the correct side; also show spread cost.
- **Basket P/L (net)** = Σ position.profit + Σ swap + Σ commission (entry commission from deals; estimated exit commission if the broker charges per side). TP/SL evaluated on **net** P/L. Configurable basis: `net` (default) or `gross`.
- **Basket TP/SL types:** absolute currency amount (as in the original), or % of balance, or points from average entry. Optional trailing basket TP (off by default).
- **Closing procedure ("verify every position"):**
  1. Set basket state `CLOSING` (blocks new entries in that basket).
  2. Send close requests for each position ticket (opposite-side deal with `position=ticket`), with proper filling mode/deviation.
  3. Re-read positions from MT5; any still open → retry with backoff (bounded), refresh prices between attempts; handle partial closes (remaining volume) and "position already closed" (10036) as success-if-verified.
  4. Only when MT5 shows **zero** positions for that basket → state `CLOSED`, record realized P/L from deals, emit event.
  5. If not all closed after N retries → raise **CRITICAL alert**, keep `CLOSING`, escalate per risk config, never mark closed.
- Basket SL is a **software stop**: it fails if the bot/PC/internet is down. See Section 50 for the mandatory broker-side protective layer.
- Basket margin used = Σ `order_calc_margin` per position (or from account margin delta if isolated); basket P/L % relative to balance at basket start.

---

## 12. POSITION SIZING

Create a proper position sizing engine.

Inputs:

- Account balance
- Equity
- Risk %
- Stop distance
- Symbol contract specifications
- Tick value
- Tick size
- Minimum lot
- Maximum lot
- Lot step

Validate every volume against broker constraints.

Never submit an invalid lot size.

**[ADD] Formulas and rules**

- `risk_amount = equity_or_balance × risk_pct` (configurable basis).
- `lots = risk_amount / ((stop_distance / tick_size) × tick_value_loss)`; use `trade_tick_value_loss` for loss sizing where available, else `trade_tick_value`. Account-currency conversion is already in tick value — do not re-convert.
- Round **down** to `volume_step` using `Decimal` (avoid float artifacts like 0.30000000000000004); then clamp to `[volume_min, min(volume_max, max_lot)]`. If risk-based lots < `volume_min` → **do not trade** (don't round up to exceed the risk budget) unless config allows.
- Validate `volume_limit` (max total volume per symbol) if non-zero, and free margin via `order_calc_margin` with a configurable safety buffer (e.g. keep ≥ X% free margin).
- Grid sizing is basket-level: also compute the **total risk if all remaining levels fill and price reaches basket SL**, not only the next order's risk.
- All sizing functions are pure and unit-tested with real-looking broker specs (2-digit gold, 100 oz contract, lot step 0.01) and edge cases (step 0.001, min 0.1, min > risk budget).

---

## 13. RISK MANAGER

Implement a hard risk-management layer independent of the strategy.

Parameters:

- Maximum daily loss
- Maximum account drawdown
- Maximum open positions
- Maximum total volume
- Maximum margin usage
- Maximum spread
- Maximum consecutive losses
- Maximum basket loss
- Maximum number of entries per hour
- Trading session

If a risk limit is triggered:

```
STOP NEW ENTRIES
        ↓
PAUSE STRATEGY
        ↓
LOG EVENT
        ↓
SHOW ALERT
```

Optional emergency mode:

```
CLOSE ALL
```

This must be configurable.

**[ADD] Definitions (so limits are testable)**

- **Trading day** = configurable boundary (default: broker server midnight); stored in UTC. Document it in RISK_MANAGEMENT.md.
- **Daily loss** = (equity now − equity at day start), i.e. **includes floating P/L**, not just realized. Configurable `daily_loss_basis`.
- **Account drawdown** = (peak equity − current equity)/peak; peak baseline configurable (`since_start_of_run` | `since_start_of_day` | `all_time`); persisted across restarts.
- **Margin usage** = margin / equity, plus a **minimum margin level %** and **minimum distance to stop-out** (read `margin_so_so`/`margin_so_call` from account info).
- **Consecutive losses** count closed **baskets** and/or deals (configurable); reset rule documented.
- Additional recommended limits (all configurable, defaults conservative): max price move per minute (volatility filter), max slippage per order, max order-rejects per hour, max API/MT5 error rate, no-trade windows (rollover, configured news windows), **weekend/close-of-week protection** (flatten or block entries before the market closes; gold gaps).
- Each limit has an **action**: `BLOCK_ENTRIES` | `PAUSE` | `CLOSE_BASKET` | `CLOSE_ALL`. Some limits **latch** (daily loss, max drawdown, kill switch) and need **manual reset** with acknowledgement; others auto-clear (spread back to normal).
- **Risk manager has veto power over everything** and runs in its own loop, so it keeps working while the strategy is paused/stopped. Strategy config cannot loosen or disable it; loosening risk limits is only possible while bot is stopped and is audit-logged.
- **Fail closed:** if account/tick/positions data is missing, stale, or inconsistent → deny entries.
- **Absolute ceilings from `.env`** (`ABSOLUTE_MAX_LOT`, `ABSOLUTE_MAX_POSITIONS`, `ABSOLUTE_MAX_TOTAL_LOTS`) that the UI/JSON config cannot exceed — a last line of defense against fat-finger configs.
- Every verdict is a structured object: `{allowed, checks:[{name, passed, value, limit}], reason}` and is stored/logged, so the UI can show *why* an entry was refused.
- Pause semantics: see Section 15 — **PAUSE stops new entries but still manages exits/risk** for open positions.

---

## 14. KILL SWITCH

Create:

```
[ EMERGENCY STOP ]
```

When activated:

```
STOP STRATEGY
STOP NEW ORDERS
CANCEL PENDING ORDERS
OPTIONALLY CLOSE OPEN POSITIONS
SET SYSTEM STATE = EMERGENCY_STOP
```

The bot must remain stopped until the user manually resets it.

**[ADD] Details**

- **Order of operations:** (1) set `EMERGENCY_STOP` **in memory and DB first** (blocks all entries instantly, survives crash/restart); (2) stop strategy loop; (3) cancel pending orders (bot-owned by default); (4) if `close_on_emergency` (configurable, default per user) → run the verified close-all procedure.
- **Idempotent and safe to press repeatedly.** Works from any state including `ERROR`/`DISCONNECTED` (it attempts what it can, reports what it couldn't, and retries closes when connection returns if `close_on_emergency` is set).
- **Scope** is explicit: `BOT_ONLY` (default: positions with the bot's magic numbers) or `ALL_ACCOUNT` (needs its own explicit button/confirmation). Never touch foreign positions silently.
- Close-all uses bounded retries with escalating deviation policy, verifies with MT5 (Section 11 closing procedure), reports remaining exposure if it fails, and raises a CRITICAL alert.
- **Reset:** only via a dedicated endpoint/button requiring typed confirmation (`RESET`) **and** a clean reconciliation. Restarting the process does **not** clear it.
- Trigger sources: UI button, API, keyboard shortcut, risk-manager escalation, optional watchdog (Section 50).
- Emergency close-all bypasses risk-manager *entry* checks and the PAUSED/ERROR state gate (Section 15) but **not** the demo check.

---

## 15. BOT STATES

Use a strict state machine:

- DISCONNECTED
- CONNECTING
- CONNECTED
- READY
- RUNNING
- PAUSED
- STOPPING
- EMERGENCY_STOP
- ERROR

Never allow an order when the system is:

- DISCONNECTED
- PAUSED
- EMERGENCY_STOP
- ERROR

unless it is an explicit emergency close operation.

**[FIX] The original rule is too blunt and creates a hazard.** Blocking *all* orders in `PAUSED` means: a risk limit pauses the strategy, positions stay open, and basket TP/SL can no longer fire. Fix by classifying orders:

| Order class | Meaning | DISCONNECTED | PAUSED | EMERGENCY_STOP | ERROR | RUNNING |
|---|---|---|---|---|---|---|
| **ENTRY** (increases exposure) | new position/grid level | ✗ | ✗ | ✗ | ✗ | ✓ (after checks) |
| **REDUCE** (close/TP/SL/basket exit, tighten SL) | reduces exposure | ✗ (impossible) | ✓ | ✓ if emergency-close | ✓ *if MT5 reachable* | ✓ |
| **EMERGENCY_CLOSE** | kill switch / close-all | attempt | ✓ | ✓ | ✓ | ✓ |

**[ADD]**

- Split into **orthogonal machines** so states aren't overloaded: `ConnectionState` (DISCONNECTED/CONNECTING/CONNECTED/ERROR), `BotState` (READY/RUNNING/PAUSED/STOPPING/EMERGENCY_STOP), and `ExecutionMode` (DRY_RUN | DEMO_EXECUTION). The 9-state list above remains the externally displayed composite state.
- Provide an **explicit transition table** (allowed `from → to → trigger → guard`). Illegal transitions raise and are logged. Property-based test: no sequence of events reaches an ENTRY order in a forbidden state.
- `EMERGENCY_STOP` is **persisted**; `ERROR` cannot silently return to `RUNNING` — it must pass through `READY` after reconciliation succeeds and the user re-starts.
- State changes are written to `system_events` and pushed on WebSocket with a monotonically increasing sequence number.
- Every order request carries the state observed at decision time and is **re-validated at send time** (state may have changed during risk checks).

---

## 16. RECONCILIATION

This is extremely important.

The bot's internal state must never be treated as more authoritative than MT5.

Every few seconds:

```
BOT STATE
   ↕
MT5 STATE
```

Compare:

- Open positions
- Volumes
- Tickets
- Symbol
- Direction
- SL
- TP
- Entry price
- Magic number

If there is a mismatch:

```
RECONCILIATION WARNING
```

Attempt to recover safely.

Examples:

- position manually closed in MT5
- order rejected
- terminal disconnected
- broker rejected modification
- partial close
- unexpected position
- duplicate order
- bot restarted

Never blindly place another trade because an internal state says a position exists when MT5 says it does not.

**[ADD] Mismatch taxonomy and safe responses**

| Situation | Detection | Response |
|---|---|---|
| Position in DB, gone in MT5 | ticket missing | Look up closing deal (`history_deals_get` by position id) → record real reason (SL/TP/stop-out/manual/client); update basket; re-evaluate grid level (no auto re-entry until cooldown + risk pass) |
| Position in MT5 with bot magic, not in DB | unknown ticket | **Adopt** into the matching basket (rebuild from comment/magic) and log; if it can't be attributed → mark `ORPHAN`, alert, do not trade around it |
| Position in MT5 with foreign/no magic | magic mismatch | Show as `FOREIGN`; **never manage or close it** unless user explicitly acts; include in account-level risk math |
| Volume decreased | partial close | Update quantity; recompute basket; log |
| SL/TP differ | field mismatch | Compare within tolerance (`point`); if bot-owned protective SL missing → re-apply; log |
| Duplicate level (two positions for one basket level) | (basket, level) key collision | Alert, freeze new entries for basket, propose corrective close (needs policy/confirmation) |
| Order sent, result unknown | in-flight record without result | Query positions/orders/deals by magic+comment+time window before any retry (Section 17) |
| MT5 unreachable | health check fails | Freeze entries, keep last-known state flagged `STALE`, retry reconnect, re-reconcile on recovery |

- Cadence: light positions check every ~1–2 s; full check (positions + pending orders + recent deals) every ~10 s; **forced full reconciliation** after every order result, on every reconnect, and at startup (before `READY`).
- Compare floats with tolerances (`point` for prices, `volume_step/2` for lots).
- **Reconciliation never opens new positions.** Its only allowed actions: update internal records, raise alerts, freeze entries, and (if configured) re-apply missing protective stops or close verified orphans.
- Reconciliation results stored (`system_events`/`reconciliation` event type) and shown in UI with a "last reconciled N seconds ago" indicator; if older than a threshold → block entries.
- A **restart must be a non-event**: the bot can be killed at any moment and, on restart, rebuild baskets, grid levels, and last-entry price purely from MT5 + DB.

---

## 17. DUPLICATE ORDER PROTECTION

Every strategy order must have:

- Magic Number
- Strategy ID
- Client/order identifier where supported

Before opening a new position:

```
CHECK EXISTING POSITIONS
CHECK LAST SIGNAL
CHECK COOLDOWN
CHECK RISK
CHECK MARGIN
CHECK DUPLICATE ORDER
```

Only then send the order.

**[FIX] MT5 has no client order ID.** The only fields available are `magic` (integer) and `comment` (**≤ 31 chars**, brokers may truncate/alter it). Therefore:

- **Magic number:** deterministically derived per `(strategy_id, direction)` into a unique 32-bit int; stored in DB; collision-checked at startup; distinct from the TEST magic.
- **Comment format** (fits 31 chars), e.g. `xg1|S|B7|L04|k9f2` = strategy short id | direction | basket | level | short nonce. Parse defensively (brokers can modify it).
- **Idempotency key = (basket_id, level).** At most one live position per key. Before every ENTRY: re-read MT5 positions **and** pending orders, confirm no existing position/order for the key.
- **In-flight lock:** only one order in flight per basket (and per strategy); a second signal while one is in flight is dropped and logged.
- **Ambiguous outcome (timeout, `None` return, connection drop mid-send):** do **not** retry blindly. Query positions/orders/recent deals by magic + comment + time window; decide *filled / not filled / unknown*. If unknown → freeze entries for that basket and alert; resolve via reconciliation.
- **One decision per tick/bar:** debounce so the same market event cannot produce two intents.
- Store the request, result, and verification in `orders`/`executions` with a shared correlation id (Section 23).

---

## 18. MARKET DATA

Create a reliable market-data service.

For XAUUSD:

- Bid
- Ask
- Spread
- Tick timestamp

Do not use stale data.

Check timestamp freshness before trading.

If market data becomes stale:

```
STOP NEW ENTRIES
```

**[ADD] Details**

- Python MT5 has **no tick callbacks**: poll `symbol_info_tick()` at a configurable rate (default 100–250 ms) on the MT5 worker thread, publish via the event bus; chart candles via `copy_rates_from_pos`; only pull `copy_ticks_*` when needed.
- **Staleness:** define `max_tick_age_ms` (configurable, default e.g. 5000). Compute age using `tick.time_msc` vs an estimate of current **server** time (Section 46), not the local PC clock. Also flag *frozen* feeds (same bid/ask for > N seconds while market is supposedly open).
- **Market closed vs stale:** use `symbol_info.trade_mode`, `symbol_info_session_trade` / session data, and tick behavior to distinguish "market closed" (expected, no alert storm) from "feed problem" (alert). Gold has a daily break and weekend close.
- Sanity checks: `bid > 0`, `ask ≥ bid`, spread within plausible range, reject/flag single-tick jumps beyond a configured threshold before feeding the strategy.
- `symbol_select(symbol, True)` at startup so the symbol is in Market Watch; verify `visible`.
- **Symbol resolution:** if configured `XAUUSD` isn't found, search candidates (`XAUUSD*`, `GOLD*`) and require the user to **confirm** the mapping once — never auto-trade a guessed symbol. Read `digits`, `point`, `trade_contract_size`, `tick_size`, `tick_value`, `volume_min/max/step`, `trade_stops_level`, `trade_freeze_level`, `filling_mode`, `trade_mode` from MT5.
- Daily high/low from the D1 bar or accumulated ticks, labeled with the day boundary used.

---

## 19. EXECUTION SAFETY

Every trade request must go through:

```
Strategy
 ↓
Risk Manager
 ↓
Validation
 ↓
Margin Check
 ↓
Broker Symbol Check
 ↓
Order Request
 ↓
MT5
 ↓
Execution Result
 ↓
Verification
 ↓
Database
 ↓
UI
```

If the broker rejects an order, show:

```
ORDER REJECTED
MT5 retcode
Description
Symbol
Volume
Price
Reason
```

Never display a successful trade until execution has been confirmed.

**[ADD] Canonical pipeline (Sections 17 and 19 merged into one implementation)**

There is exactly **one** code path: `ExecutionService.submit(intent)`. Nothing else may reach `MT5Gateway.send_order`. Steps:

1. **Intent** from strategy (or user action) — includes class ENTRY/REDUCE/EMERGENCY, correlation id, config hash.
2. **State gate** (Section 15 matrix).
3. **Duplicate/idempotency checks** (Section 17).
4. **Risk manager** verdict (stored).
5. **Validation:** symbol tradable, volume vs min/max/step/`volume_limit`, prices vs `stops_level`/`freeze_level`, SL/TP on correct side, spread ≤ max, tick fresh, demo verified.
6. **Margin check:** `order_calc_margin` vs free margin + buffer.
7. **`order_check`** (MT5 dry validation) — reject if retcode isn't OK.
8. **Build request:** correct price (BUY=ask, SELL=bid), `deviation` (configurable slippage tolerance), **filling mode chosen from `symbol_info.filling_mode`** (FOK/IOC/RETURN; never hardcode), `type_time`, magic, comment, protective SL (Section 50).
9. **`order_send`** with timeout budget. `None` result → capture `last_error()`.
10. **Interpret retcode** via table in Section 49 (`DONE`, `DONE_PARTIAL`, requote, off quotes, etc.). Retry **only** for safe, transient retcodes, bounded, with fresh price, re-running checks 2–7. Never retry after ambiguous outcomes (Section 17).
11. **Verify with MT5:** confirm the position/deal exists with expected volume/price (allowing for slippage), or confirm closure for REDUCE orders.
12. **Persist** request, response, verification, latency, slippage, retcode, correlation id.
13. **Publish** to UI; a trade is shown as "OPEN" only after step 11.

Rejected order UI card includes: retcode (numeric + name), MT5 comment, symbol, requested volume/price, deviation, filling mode used, `last_error`, and a **plain-English reason + suggested fix**.

---

## 20. REAL-TIME P/L

The dashboard must calculate and display:

- Floating P/L
- Realized P/L
- Today's P/L
- Basket P/L
- Total P/L

But the primary values must come from actual MT5 account/position data.

Do not simulate profits.

**[ADD]** Definitions: **Floating** = from open positions (MT5); **Realized** = Σ(profit + commission + swap + fee) of closing deals in the period (MT5 history); **Today** = realized today + change in floating (define precisely; day boundary from Section 13); **Basket** = Section 11; **Total** = realized over selected period + current floating. All in **account currency**. Values carry provenance tags (Section 1). A reconciliation check compares dashboard totals to `account_info` (equity − balance vs Σ floating) and flags discrepancies beyond a tolerance.

---

## 21. VIDEO-STYLE MODE

Create a special configuration called:

```
AGGRESSIVE DEMO MODE
```

This mode is for experimentation on demo accounts only.

It should allow:

- Many positions
- Grid entries
- Configurable lot multiplier
- Basket TP
- Basket SL
- Fast re-entry
- High position count

But the UI must prominently show:

```
⚠ AGGRESSIVE MODE
DEMO ACCOUNT ONLY
HIGH RISK
```

Do not claim that this strategy can reproduce the profit shown in the reference video.

**[ADD]** Off by default; enabling requires typed confirmation; the banner is persistent on every page while enabled; **all hard caps still apply** (Risk Manager, absolute `.env` ceilings, demo enforcement, worst-case preview). "Aggressive" widens configurable ranges (e.g. up to 50 positions, faster cooldown) but never removes safety checks. Log every activation.

---

## 22. STRATEGY CONFIGURATION

Store strategies as JSON/YAML configuration rather than hardcoding parameters.

Example:

```json
{
  "strategy_id": "xauusd_grid_demo",
  "symbol": "XAUUSD",
  "enabled": false,
  "direction": "SELL",
  "initial_lot": 0.01,
  "lot_mode": "fixed",
  "lot_multiplier": 1.0,
  "max_lot": 1.0,
  "max_positions": 20,
  "grid_distance_points": 100,
  "basket_take_profit": 10.0,
  "basket_stop_loss": 20.0,
  "cooldown_seconds": 60
}
```

Validate all configuration values before allowing the strategy to start.

**[FIX/ADD] Extended example** (original keys preserved; new keys added; amounts are in **account currency**, `basket_stop_loss` is a **positive magnitude of loss**):

```json
{
  "schema_version": 1,
  "strategy_id": "xauusd_grid_demo",
  "symbol": "XAUUSD",
  "symbol_broker_alias": null,
  "enabled": false,
  "mode": "DRY_RUN",
  "direction": "SELL",
  "grid_mode": "adverse",
  "grid_anchor": "last_entry",
  "first_entry": "manual_trigger",
  "initial_lot": 0.01,
  "lot_mode": "fixed",
  "lot_multiplier": 1.0,
  "allow_multiplier": false,
  "custom_lots": [],
  "max_lot": 0.05,
  "max_total_lots": 0.20,
  "max_positions": 20,
  "grid_distance_points": 100,
  "basket_take_profit": 10.0,
  "basket_stop_loss": 20.0,
  "basket_pnl_basis": "net",
  "protective_sl_points": 5000,
  "max_slippage_points": 30,
  "max_spread_points": 60,
  "cooldown_seconds": 60,
  "rearm_after_basket_close": false,
  "rearm_delay_seconds": 300,
  "max_entries_per_hour": 20,
  "sessions": {"timezone": "UTC", "allowed": [["07:00", "20:00"]]},
  "aggressive_mode": false
}
```

**[ADD] Validation rules**

- Validate with Pydantic + publish a JSON Schema; reject unknown keys; explicit units; explicit types (no stringly numbers).
- Cross-field checks (examples): `initial_lot ≥ volume_min`; `max_lot ≥ initial_lot`; `max_total_lots ≥ Σ planned lots`; `lot_multiplier > 1 ⇒ allow_multiplier`; `direction=BOTH ⇒ hedging account`; `basket_stop_loss ≤ risk.max_basket_loss`; `max_positions ≤ ABSOLUTE_MAX_POSITIONS`; grid distance ≥ N × typical spread; worst-case exposure preview passes.
- Config is **versioned**: each save writes a `config_versions` row (hash, author, timestamp, diff). Each `strategy_run` records the config hash actually used.
- Config **cannot change while RUNNING**; change requires PAUSE/STOP, re-validation, and re-confirmation. No silent hot reload.
- Pick one format (JSON) for V1 and document it; YAML optional later.

---

## 23. LOGGING

Create structured logs.

Every event should include:

- Timestamp
- Level
- Component
- Account
- Symbol
- Strategy
- Action
- Order ticket
- Position ticket
- Result
- MT5 retcode
- Message

Log:

- connection
- disconnection
- reconnection
- signal
- order request
- order result
- position opened
- position closed
- SL modification
- TP modification
- risk violation
- kill switch
- errors
- reconciliation

**[ADD]**

- JSON-lines format, UTC timestamps, rotating files + DB `system_events`; log levels used consistently.
- **`correlation_id`** ties one intent through risk → request → result → verification → UI. Add `basket_id`, `config_hash`, `mode` (DRY/DEMO).
- **Redaction:** passwords/tokens/full account credentials never logged; a unit test feeds secrets through the logger and asserts they don't appear. Account login may be partially masked in shared logs.
- A separate **append-only audit log** for control actions (start/stop/pause/emergency/config change/mode change/close-all) with who/when/from where.
- Log viewer page: filter by level/component/strategy/time/correlation id; live tail via WebSocket; export.
- Don't spam: rate-limit repetitive identical warnings (e.g. stale-data) but count them.

---

## 24. DATABASE SCHEMA

Create tables similar to:

- accounts
- strategies
- strategy_runs
- orders
- positions
- executions
- pnl_snapshots
- risk_events
- system_events
- errors

Use migrations.

Do not create an unnecessarily complicated database.

**[ADD]** Minimal additions only: `bot_state` (singleton row: state, emergency flag, last confirmed login/server, peak equity), `connection_tests`, `config_versions`. Also: Alembic migrations from day one; UTC timestamps; `NUMERIC` money; indexes on `(ticket)`, `(magic, time)`, `(strategy_run_id, time)`; unique constraint on `(basket_id, level)` for live positions; foreign keys; `pnl_snapshots` written at a sane cadence (e.g. every 5–60 s + on change) with retention/compaction; DB write failures must **not** block emergency actions (log and continue); tests run migrations up/down on both SQLite and PostgreSQL.

---

## 25. API

Create FastAPI endpoints such as:

```
GET  /api/health
GET  /api/mt5/status
POST /api/mt5/connect
POST /api/mt5/disconnect

GET  /api/account
GET  /api/market/xauusd

GET  /api/positions
GET  /api/orders
GET  /api/history

POST /api/trading/start
POST /api/trading/pause
POST /api/trading/stop
POST /api/trading/emergency-stop
POST /api/trading/close-all

GET  /api/strategy
POST /api/strategy
PUT  /api/strategy/{id}

GET  /api/risk
PUT  /api/risk
```

Add WebSocket:

```
/ws
```

for:

- prices
- account updates
- positions
- P/L
- bot state
- alerts
- logs

**[ADD] Additional endpoints**

```
POST /api/mt5/test                     # run connection test (Section 5)
GET  /api/mt5/test/latest
GET  /api/symbols/resolve?query=XAU
GET  /api/symbols/{symbol}/spec        # contract specs used for sizing
POST /api/trading/mode                 # DRY_RUN <-> DEMO_EXECUTION (confirmation token)
POST /api/trading/start-request        # returns confirmation nonce (two-step start)
POST /api/trading/reset-emergency      # typed confirmation + clean reconciliation
POST /api/positions/{ticket}/close
PUT  /api/positions/{ticket}           # modify SL/TP
POST /api/baskets/{id}/close
DELETE /api/orders/{ticket}            # cancel pending
GET  /api/baskets
GET  /api/exposure-preview             # worst-case preview (Section 10)
GET  /api/reconciliation/status
GET  /api/logs      GET /api/events    GET /api/audit
GET  /api/metrics?from=&to=&strategy=  # Section 33
GET  /api/performance
POST /api/backtest                     # Phase 10
```

**[ADD] API rules**

- **Authentication is mandatory** (this API can move money-like state): random local API token generated at first run (or login), required on every REST call and on the WebSocket handshake; bind to `127.0.0.1` by default; CORS restricted to the frontend origin; WebSocket `Origin` check; simple rate limits; CSRF protection if cookies are used (Section 34).
- Control endpoints (`start`, `pause`, `stop`, `emergency-stop`, `close-all`, `mode`) are **idempotent** (accept an idempotency key), return the resulting state, and are audit-logged. `start` requires the two-step confirmation nonce.
- Uniform error format: `{code, message, details, correlation_id}`; never leak stack traces or secrets. Versioned OpenAPI docs; typed response models; pagination on list endpoints.
- **WebSocket protocol:** on connect send a **full snapshot** (state, account, positions, baskets, last N alerts), then **deltas** with a sequence number; client detects gaps and re-syncs; heartbeat/ping; server-side throttling (e.g. price ≤ 4–10 msgs/s); backpressure (drop stale price frames, never drop alerts/state changes); automatic client reconnect with backoff; UI shows "LIVE / RECONNECTING / STALE".

---

## 26. FRONTEND PAGES

Create:

```
/dashboard
/positions
/orders
/history
/strategy
/risk
/logs
/settings
```

Dashboard should be the primary terminal.

**[ADD]** Also `/connection-test` (Section 5) and `/performance` (Section 33). A global header on **every page** shows: connection state, DEMO badge, mode (DRY/DEMO EXEC), bot state, aggressive-mode banner, and an always-visible EMERGENCY STOP.

---

## 27. DASHBOARD LAYOUT

Use a professional trading-terminal layout.

Top:

```
MT5 CONNECTION
● CONNECTED
DEMO
Server: XXXXX
```

Account cards:

```
BALANCE
EQUITY
FLOATING P/L
FREE MARGIN
MARGIN LEVEL
```

Main:

```
XAUUSD CHART
```

Right panel:

```
BOT STATUS
RUNNING

Strategy
XAUUSD Grid

Positions
8

Basket P/L
+$142.35

[ PAUSE ]
[ CLOSE ALL ]
[ EMERGENCY STOP ]
```

Bottom:

```
OPEN POSITIONS
TRADE LOG
SYSTEM EVENTS
```

**[ADD]** Right panel also shows: mode, why-not-trading reason, risk meters (daily loss %, drawdown %, margin usage %, exposure vs caps), reconciliation age, data age. Chart overlays average entry line, basket TP/SL levels, and position markers. Sample values above are illustrative only.

---

## 28. UI REQUIREMENTS

Do NOT make the UI decorative or overloaded.

Prioritize:

- information density
- readability
- clear status
- fast controls
- visible risk
- error visibility

Use color only where semantically useful:

- green = profit/healthy
- red = loss/error/emergency
- yellow = warning
- neutral = information

Do not hide important information behind multiple menus.

**[ADD]** Never rely on color alone (add icons/text for colorblind users). Numeric cells use tabular figures and consistent decimals per symbol `digits`. Stale/disconnected data is greyed with a visible badge — never show frozen numbers as if live. Destructive actions have clear, minimal confirmation; the kill switch is one click + one confirm. Dark theme default. Error toasts persist until acknowledged for CRITICAL alerts. Keyboard shortcut for pause/emergency (with modifier to prevent accidents). Accessibility basics (focus states, labels).

---

## 29. REFERENCE VIDEO ANALYSIS

The supplied video is only a behavioral reference.

Analyze it if technically possible and identify:

- Approximate number of positions
- BUY/SELL direction
- Position size progression
- Entry spacing
- Visible TP/SL behavior
- Account balance/equity changes
- Order frequency

But explicitly separate:

```
OBSERVED FROM VIDEO
```

from:

```
ASSUMED / UNKNOWN
```

Do not invent missing strategy rules.

If exact strategy parameters cannot be determined from the video, make them configurable rather than guessing.

**[FIX/ADD]**

- **No video file is attached to this prompt text.** If the user has not provided one in the working environment, state that, **skip this section**, and do not fabricate observations.
- If a video file is provided: check tooling (`ffmpeg`), extract frames at a stated rate, and read values from frames (OCR or visual). Output a table with three columns: **OBSERVED** (with timestamp/frame reference), **INFERRED** (labeled inference + confidence), **UNKNOWN**. Screen recordings can be edited, cherry-picked, from demo accounts, or from different symbols/timeframes; treat every profit claim as **unverified** and never use it as a target or acceptance criterion.
- Output of this analysis feeds only into **default values of configurable parameters** (clearly marked "sample, not validated"), never into hardcoded logic.

---

## 30. TESTING

Create automated tests for:

**Unit tests**

- lot calculation
- basket P/L
- weighted average entry
- risk limits
- grid calculations
- configuration validation
- state transitions

**Integration tests**

- MT5 connection
- account information
- symbol information
- market data
- demo order
- position retrieval
- position close
- history verification

**Failure tests**

Simulate:

- MT5 disconnected
- Broker rejects order
- Insufficient margin
- Invalid volume
- Stale price
- Duplicate order
- Position manually closed
- Bot restart
- Network failure

The bot must fail safely.

**[FIX] Contradiction resolved.** Section 43 forbids fake MT5 data, but failure simulation *requires* fakes. Rule: **fakes/mocks (`FakeGateway`, scripted broker responses) exist only under `tests/`, are never importable from runtime code, and can never be selected by config.** Runtime never fabricates data.

**[ADD] Test plan**

- **Isolation:** the `MetaTrader5` import lives only in `backend/app/mt5/`. Unit/failure tests run on any OS/CI without MT5. Integration tests are marked `@pytest.mark.mt5_integration`, run only on the Windows machine with `RUN_MT5_INTEGRATION=1`, and **refuse to run unless the account is DEMO**.
- **More unit tests:** demo-verification logic (real/contest/unknown → refuse), lot rounding with `Decimal`, retcode mapping, comment/magic parsing, idempotency key collisions, risk verdicts (each limit + latching + reset), day-boundary/timezone math, staleness math, exposure preview, config cross-field validation, close-procedure state machine, log redaction, transition table property tests.
- **More failure tests:** netting account with grid config; algo trading disabled; market closed; requote/off quotes/too many requests; `order_send` returns `None`; timeout with unknown outcome (order actually filled); partial fill; partial close; broker modifies comment; SL/TP too close (invalid stops); frozen feed; server/login switched mid-session; clock skew; weekend gap through basket SL; stop-out event; DB unavailable; WebSocket disconnect/reconnect; two backend instances started; process killed mid-order then restarted; kill switch while disconnected; close-all where some closes fail.
- **Coverage targets:** ≥ 90% line/branch on `risk/`, execution pipeline, state machine, sizing, reconciliation; overall ≥ 80%.
- **Static quality gates:** `ruff`, `mypy --strict` on trading/risk/mt5 packages, `eslint` + `tsc --noEmit`, pre-commit hooks, secret scanning (e.g. gitleaks), `pip-audit`/`npm audit`.
- **Frontend tests:** component tests (Vitest) for P/L formatting, stale badges, state banners; Playwright smoke test against a **test-mode backend that uses FakeGateway** (test-only launcher) to verify buttons/flows.
- **CI:** GitHub Actions (or equivalent) runs all non-MT5 tests on Linux; MT5 integration tests are documented as a manual/local step with evidence attached to the phase report.

---

## 31. PAPER/DRY-RUN MODE

Before real demo execution, implement:

```
DRY RUN = ON
```

In dry-run mode:

- receive real XAUUSD market data
- generate strategy signals
- calculate theoretical orders
- do NOT send orders to MT5
- show what would have happened

Example:

```
SIGNAL

XAUUSD SELL

Would open:
0.01 lot

Reason:
Grid condition satisfied

Risk:
PASS

MT5 ORDER:
NOT SENT — DRY RUN
```

Then allow:

```
DRY RUN
    ↓
DEMO EXECUTION
```

**[ADD]**

- **Default at first start: DRY RUN = ON.** Switching to DEMO EXECUTION requires: demo verified, connection test passed (Section 5), valid config + exposure preview passing, typed confirmation, and (configurable) a minimum dry-run observation period.
- Implemented as a **`DryRunGateway`** substituted at the same seam as `Mt5Gateway`, so **the same strategy → risk → validation → pipeline code runs** in both modes (only the final gateway differs). This prevents "works in dry-run, breaks in demo" divergence.
- Virtual fills use the **real bid/ask** (BUY at ask, SELL at bid) plus configured slippage; virtual P/L computed with symbol specs (`order_calc_profit` / tick value), commission and swap estimated and labeled as such.
- Virtual positions/baskets/PnL live in **separate `virtual_*` tables** and UI widgets labeled `THEORETICAL — DRY RUN`; they are never summed with, or displayed as, MT5 account values.
- Dry-run still honors risk limits, cooldowns, max positions, staleness, and market hours; it logs "would have been rejected because…".
- The bot cannot be in dry-run and demo execution simultaneously; the mode is shown on every page and stamped on every log/event.

---

## 32. BACKTESTING

Create a strategy interface that can later be connected to a historical backtesting engine.

The same strategy logic should ideally support:

```
Historical Data
      ↓
Backtest Engine
```

and:

```
Live Demo Data
      ↓
MT5 Execution
```

Avoid creating two completely different strategy implementations.

**[ADD] Interface contract**

```python
class Strategy(Protocol):
    def on_market(self, snapshot: MarketSnapshot, portfolio: PortfolioSnapshot,
                  clock: Clock) -> list[OrderIntent]: ...
    def on_fill(self, fill: Fill) -> None: ...
    def state(self) -> StrategyState: ...    # serializable, rebuildable from MT5 + DB
```

- Strategies are **pure/deterministic**: no MT5 imports, no `datetime.now()` (injected `Clock`), no DB/network access, no global state. They emit intents; they do not send orders.
- One `ExecutionGateway` abstraction with three implementations: `Mt5Gateway`, `DryRunGateway`, `BacktestGateway`.
- Strategy state must be reconstructable from portfolio snapshot (needed for restart safety **and** for backtest determinism).
- The same unit tests run a strategy against a scripted price path and assert identical intents regardless of gateway.

---

## 33. PERFORMANCE METRICS

Dashboard should eventually show:

- Total Trades
- Winning Trades
- Losing Trades
- Win Rate
- Gross Profit
- Gross Loss
- Profit Factor
- Average Win
- Average Loss
- Largest Win
- Largest Loss
- Maximum Drawdown
- Average Trade
- Total Fees/Commission

Do not present these metrics without clearly specifying the measurement period.

**[ADD]**

- Document each formula in TRADING_ENGINE.md; compute from **MT5 deals** (net of commission/swap/fees), by position/basket, with selectable period, strategy, direction, and mode (DEMO only; never mix with THEORETICAL).
- **Maximum Drawdown** measured on the **equity** curve (sampled from `pnl_snapshots`), not on closed-trade profit only; state sampling resolution.
- **Grid-specific metrics** (win rate alone is misleading for grid systems: many small wins, rare very large losses): worst basket loss, max adverse excursion, max open lots, max simultaneous positions, time in drawdown, average basket duration, **expectancy per basket**, loss-to-win ratio, tail-loss summary.
- Show sample size warnings ("n = 12 baskets — statistically weak").
- Every metric card displays its period, count of trades, and data source.

---

## 34. SECURITY

Never:

- hardcode passwords
- commit ".env"
- expose credentials through frontend
- print passwords in logs
- send credentials to third-party services
- store plaintext credentials unnecessarily

Add:

- `.env.example`
- `.gitignore`

with secrets excluded.

**[ADD]**

- **Control-plane security:** local-only binding (`127.0.0.1`), API token auth on REST + WebSocket, CORS allowlist, WS Origin check, rate limiting, CSRF protection for cookie sessions, security headers, HTTPS/reverse proxy required if ever exposed beyond localhost (and then strong auth + IP allowlist). An unauthenticated trading API is a critical vulnerability.
- Prefer attaching to an already-logged-in terminal (no password handled). If a password is needed, hold it only in memory as `SecretStr`; optionally use Windows Credential Manager/`keyring` instead of `.env`.
- `.gitignore` must include: `.env`, `*.env.*` (except `.env.example`), `*.db`, `*.sqlite*`, `logs/`, `node_modules/`, `__pycache__/`, `.venv/`, data exports, MT5 terminal files/screenshots.
- Never send account numbers, balances, or logs to third parties; telemetry/alerts (e.g. Telegram/email) are **optional, off by default, and must exclude credentials**.
- Pin dependencies (lockfiles), run `pip-audit`/`npm audit`, secret-scan pre-commit, minimal privileges (do not run the backend as Administrator unless required by MT5).
- Confirmation tokens for dangerous actions are validated on the server.
- A test proves no secret appears in logs, API responses, or the frontend bundle.

---

## 35. PROJECT STRUCTURE

Use a clean structure such as:

```
mt5-trading-terminal/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/
│   │   ├── services/
│   │   ├── trading/
│   │   ├── risk/
│   │   ├── mt5/
│   │   ├── database/
│   │   └── websocket/
│   │
│   ├── tests/
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── types/
│   │   └── App.tsx
│   └── package.json
│
├── strategies/
│   └── xauusd_grid.json
│
├── .env.example
├── .gitignore
├── README.md
└── docker-compose.yml
```

**[ADD] Additions**

```
├── backend/
│   ├── alembic.ini + migrations/
│   ├── app/trading/  strategy_base.py, grid.py, baskets.py, sizing.py, execution_service.py, state_machine.py, dryrun.py
│   ├── app/risk/     manager.py, limits.py, verdict.py
│   ├── app/services/ market_data_service.py, reconciliation_service.py, event_bus.py, audit.py
│   ├── tests/        unit/ integration/ failure/ fakes/ (fakes are test-only)
│   ├── pyproject.toml / requirements.lock
├── frontend/         vitest + playwright config, eslint, tsconfig strict
├── schemas/          strategy.schema.json, risk.schema.json
├── scripts/          preflight.py (Phase 0/1 environment check), dev_start.ps1
├── mql5/  (optional) watchdog EA (Section 50)
├── docs/             PROGRESS.md, DECISIONS.md, ARCHITECTURE.md, TRADING_ENGINE.md,
│                     RISK_MANAGEMENT.md, MT5_INTEGRATION.md, RUNBOOK.md, SECURITY.md, TESTING.md
├── .github/workflows/ci.yml
└── docker-compose.yml   # PostgreSQL (+ optional static frontend) ONLY — not MT5 (Section 0.2)
```

---

## 36. DEVELOPMENT ORDER

Do NOT attempt to build everything at once.

Implement in this exact order:

**Phase 1 — Environment**

Install and verify:

- Python
- Node.js
- MT5
- MetaTrader5 Python package
- FastAPI
- React

Verify imports and environment.

---

**Phase 2 — MT5 Adapter**

Implement:

- connect
- disconnect
- account_info
- symbol_info
- tick
- positions
- orders
- history

Test every function.

---

**Phase 3 — Demo Connection**

Connect to the user's demo MT5 account.

Verify:

- account
- server
- balance
- equity
- XAUUSD
- bid
- ask
- spread

---

**Phase 4 — One Trade**

Implement:

```
BUY 0.01
```

Then:

- verify position
- show P/L
- close position
- verify history

Do not proceed until this is reliable.

---

**Phase 5 — Dashboard**

Build:

- account
- market
- positions
- P/L
- connection status
- controls

---

**Phase 6 — Risk Manager**

Implement all hard safety checks.

---

**Phase 7 — Strategy Engine**

Implement configurable XAUUSD grid/basket strategy.

---

**Phase 8 — Real-Time WebSocket**

Push:

- price
- P/L
- positions
- bot state
- events

to the frontend.

---

**Phase 9 — Reconciliation**

Continuously synchronize internal state with MT5.

---

**Phase 10 — Backtesting**

Connect the strategy to historical data.

**[FIX] Dependency problems in the original order**

1. **Phase 0 (new): prerequisites and decisions** — OS check (Windows required), confirm items in Section 0.3, create project skeleton, `scripts/preflight.py`, CI skeleton, DECISIONS/PROGRESS docs. If the OS/environment cannot run MT5, report and stop the MT5-dependent phases.
2. **Phase 4 places real (demo) trades before Phase 6 builds the Risk Manager.** Fix: the **minimal guardrails ship in Phase 2's gateway**: demo verification, state gate, hard volume cap (`ABSOLUTE_MAX_LOT`, test volume only), stop-on-first-error, and the "one choke point" rule. Phase 4 is therefore safe from the start.
3. **Dry-run (Section 31) and exposure preview (Section 10) belong in Phase 7**, before any strategy trades in demo execution.
4. **Reconciliation (Phase 9) is too late** for a strategy that opens many positions. Fix: build a **basic** reconciliation (positions vs DB, adopt/orphan) in Phase 4/5, and complete the full service in Phase 9. Strategy execution (Phase 7 demo execution) must not be enabled until basic reconciliation exists.
5. **Phase 3 needs credentials** — the user configures `.env` locally; the agent never asks for secrets in chat.
6. **WebSocket protocol and API auth** (Section 25/34) are needed by Phase 5, not only Phase 8: implement auth in Phase 5; snapshot+delta protocol can be finalized in Phase 8.

**[ADD] Gate for every phase:** *Exit criteria* (tests passing, evidence pasted, docs updated) → PHASE REPORT (Section 52) → user approval → next phase. Suggested exit criteria per phase are the matching Section 42 checklist items.

---

## 37. STARTUP BEHAVIOR

When the application starts:

1. Load configuration
2. Validate configuration
3. Initialize database
4. Initialize MT5
5. Verify account
6. Verify DEMO status
7. Verify XAUUSD
8. Start market-data service
9. Start reconciliation service
10. Start API
11. Start WebSocket
12. Set bot state = READY

Do NOT automatically start trading.

The user must explicitly press:

```
START BOT
```

**[ADD] Refined startup (all original steps kept, additional checks inserted)**

0. **Acquire single-instance lock** (lock file/DB advisory lock). A second instance must refuse to start — two bots on one account is a duplicate-order disaster.
1. Load configuration (`.env` + strategy JSON + risk config).
2. Validate configuration (schema, cross-field, absolute ceilings, `DEMO_ONLY` must be true).
3. Initialize database + **run migrations**; load persisted `bot_state` (**if `EMERGENCY_STOP` was persisted, stay in it**).
4. Initialize MT5 (health checks: terminal connected, algo trading allowed, version).
5. Verify account (login/server matches expectation; login not changed).
6. Verify DEMO status (fail closed) and **margin mode** (hedging/netting).
7. Verify XAUUSD (resolve symbol, select, read specs, trade mode).
8. Check **clock/server-time offset** (Section 46).
9. Start market-data service.
10. **Load existing positions and adopt/classify** (BOT / MANUAL / FOREIGN / ORPHAN) and run an initial full reconciliation.
11. Start reconciliation service + risk manager loop.
12. Start API + WebSocket. (**The API may start earlier in a diagnostics-only mode** so the UI can display startup failures; trading endpoints stay disabled until step 13.)
13. Set state = **READY** only if every previous step succeeded. Any failure → `ERROR` with a specific message; never partially "ready".

Do NOT automatically start trading — the user must explicitly press `START BOT` (two-step confirmation, Section 2). Default mode after startup is **DRY RUN**.

---

## 38. SHUTDOWN BEHAVIOR

When shutting down:

```
STOP NEW ENTRIES
SAVE STATE
CLOSE DATABASE CONNECTIONS
DISCONNECT SERVICES
```

Do NOT automatically close positions unless the user has explicitly configured that behavior.

**[ADD]**

- Handle `SIGINT`/`SIGTERM`/console-close/Windows service stop; also survive hard kills (state is rebuildable from MT5 + DB).
- On shutdown with open positions: log and show a clear warning — "**N positions remain open and are NOT being managed**; they rely on broker-side protective stops (Section 50)."
- Flush logs, persist peak equity / state, release the instance lock, stop threads in order (strategy → execution → market data → MT5 worker), then `mt5.shutdown()`.
- Optional config `close_on_shutdown` (default false).

---

## 39. CRITICAL ACCOUNTING RULE

The system must never calculate fake profit from:

```
entry_price - current_price
```

alone.

For actual account P/L, account for:

- volume
- contract specifications
- tick size
- tick value
- direction
- commission
- swap
- broker execution

Prefer actual MT5 position/account values wherever available.

The dashboard's account values must reconcile with MT5.

**[FIX/ADD]**

- **Commission is not a field of MT5 `TradePosition`**; it lives on **deals**. To include it: read entry deals by `position_id` (`history_deals_get(position=...)`) and add commission (and fee) to the position's net P/L; add estimated exit commission if the broker charges per side (configurable, labeled as estimate).
- **Floating position net P/L** = `position.profit + position.swap + entry commission/fees` (+ estimated exit commission if configured). `position.profit` is already in account currency.
- For **hypothetical P/L** (e.g. "if price reaches X" in exposure preview, dry-run) use `mt5.order_calc_profit(...)` or the tick-value formula: `(Δprice / tick_size) × tick_value × volume × direction` — **never** raw `Δprice`.
- **Reconciliation test (mandatory, empirical):** with several open demo positions, compare `account_info.profit`, `equity − balance`, `Σ position.profit`, and `Σ swap`; document exactly how this specific broker relates them in MT5_INTEGRATION.md and set the reconciliation tolerance accordingly. Do not assume.
- SELL positions are valued at **ask**, BUY at **bid**; spread is a real cost visible in the basket P/L.
- Currency: account-currency P/L only; never mix quote-currency figures.

---

## 40. NO LOOK-AHEAD / NO FAKE BACKTEST

When backtesting:

- no future candles
- no future prices
- no future spread
- no future execution information
- realistic execution assumptions
- include spread
- include commission where applicable
- account for slippage where modeled

Do not optimize and report a strategy using information from the future.

**[ADD] Backtest requirements**

- **Data:** prefer tick data (`copy_ticks_range`) for grid/basket logic (bid/ask available); if using bars, use per-bar spread and document the approximation. Run data-quality checks (gaps, duplicates, timezone, holidays).
- **Execution model:** BUY at ask/SELL at bid, configurable slippage, latency, commission per lot, swap (including triple-swap day), contract size/tick value from real symbol specs, min/max/step lot rounding, `stops_level`.
- **Account simulation:** margin, margin level, **stop-out**, free margin — grid strategies fail through margin/stop-out, so this is not optional.
- **Bar-based conflicts:** if TP and SL are both inside one bar, assume the **worse** outcome; never fill on the bar's close using information from that same bar unless the live system could do so.
- **Anti-overfitting:** train/validation/out-of-sample split (walk-forward); report the number of parameter combinations tried; show parameter sensitivity, not just the best run; report **max drawdown, worst basket, time to recovery, ruin risk**, not only net profit.
- Reports carry data range, symbol, broker data source, assumptions, and parameters, and state plainly that backtest results are not predictions.
- Optional cross-check: the built-in MT5 Strategy Tester (via an MQL5 port) for validating the simulator's execution assumptions.

---

## 41. DOCUMENTATION

Create a complete README explaining:

- What the system does
- Architecture
- Requirements
- MT5 installation
- Demo account setup
- Environment variables
- How to start backend
- How to start frontend
- How to connect MT5
- How to run connection test
- How to enable dry run
- How to enable demo trading
- How to configure strategy
- How to stop bot
- How to emergency stop
- Troubleshooting

Also create:

- ARCHITECTURE.md
- TRADING_ENGINE.md
- RISK_MANAGEMENT.md
- MT5_INTEGRATION.md

**[ADD]** Also: `RUNBOOK.md` (incident procedures: MT5 disconnected with open positions, orphan position, kill switch won't close, restart after crash, how to verify state in the MT5 terminal), `SECURITY.md`, `TESTING.md`, `DECISIONS.md`, `PROGRESS.md`. README must include a **prominent risk disclosure** (Section 0.4/52), the Windows-only note (Section 0.2), and a **troubleshooting table** (symptom → cause → fix) covering: `initialize()` failure/-10003, authorization failed (-6), algo trading disabled (-8, 10027), no symbol/`XAUUSD` alias, market closed (10018), invalid stops (10016), unsupported filling mode (10030), netting-account problem, stale ticks, time-offset problems, "port already in use", second instance refused. Docs must match actual behavior (update in the same commit as code changes); ARCHITECTURE.md includes a component/sequence diagram of the order pipeline.

---

## 42. ACCEPTANCE CRITERIA

The project is NOT complete until all of these work:

**MT5**

- [ ] MT5 terminal detected
- [ ] Demo account connected
- [ ] Account information displayed
- [ ] XAUUSD detected
- [ ] Live price displayed
- [ ] Spread displayed
- [ ] Demo order submitted
- [ ] Position verified
- [ ] P/L displayed
- [ ] Position closed
- [ ] Trade history verified

**Terminal**

- [ ] Dashboard works
- [ ] Positions page works
- [ ] History works
- [ ] Strategy settings work
- [ ] Risk settings work
- [ ] Logs work
- [ ] WebSocket updates work

**Trading Engine**

- [ ] Strategy starts
- [ ] Strategy pauses
- [ ] Strategy stops
- [ ] Grid entries work
- [ ] Basket TP works
- [ ] Basket SL works
- [ ] Maximum positions enforced
- [ ] Maximum lot enforced
- [ ] Risk limits enforced
- [ ] Duplicate trades prevented

**Safety**

- [ ] Demo-only verification
- [ ] Emergency stop
- [ ] Close all
- [ ] Reconnection
- [ ] Reconciliation
- [ ] Broker error handling
- [ ] No credentials in source
- [ ] No fake P/L
- [ ] No automatic live trading

**[ADD] Additional criteria**

*MT5 / environment*
- [ ] Algo-trading-disabled and margin-mode (hedging/netting) detected and reported
- [ ] Symbol resolution, contract specs, filling mode read from broker (nothing hardcoded)
- [ ] Server-time offset handled; timestamps correct in UTC/server/local views
- [ ] Empirical account-P/L reconciliation documented (Section 39)

*Engine*
- [ ] Dry-run uses the same pipeline as demo execution; THEORETICAL data never mixed with MT5 data
- [ ] Worst-case exposure preview blocks unsafe configs
- [ ] Lot rounding to broker step verified (requested vs effective shown)
- [ ] Basket closing verified against MT5, including partial-failure retry/escalation
- [ ] PAUSED still manages exits; ENTRY orders impossible in forbidden states (property test)
- [ ] Ambiguous order outcomes never cause blind retries

*Safety*
- [ ] Order refused when account is REAL/CONTEST/unknown (test with scripted account info)
- [ ] Mid-session login/server change blocks entries
- [ ] Kill switch works from ERROR/DISCONNECTED states, persists across restart, needs manual reset
- [ ] Bot restart adopts existing positions; no duplicate entries after restart
- [ ] Second instance refused
- [ ] Stale/frozen data blocks entries; market-closed handled without alert storm
- [ ] Protective broker-side SL applied (or explicit, logged waiver in demo config) (Section 50)
- [ ] Control API requires authentication; WebSocket origin/auth checked
- [ ] Secrets absent from logs, API responses, frontend bundle (tested)

*Quality / evidence*
- [ ] Every checked item links to a test name, log excerpt, or screenshot in `docs/PROGRESS.md`
- [ ] Coverage targets and static-analysis gates met (Section 30)
- [ ] README, RUNBOOK and troubleshooting match actual behavior; risk disclosure present

---

## 43. CODING RULES

Write actual working code.

Do NOT respond with only pseudocode.

Do NOT skip implementation details.

Do NOT create placeholder functions such as:

```python
pass
```

for core functionality.

Do NOT use fake MT5 data.

Do NOT simulate successful orders.

Do NOT claim that a component works without testing it.

Use:

- type hints
- structured exceptions
- logging
- configuration validation
- modular services
- dependency injection where useful
- clean separation between UI, strategy, risk and execution

Keep the trading engine independent from the frontend.

**[ADD]**

- **Clarification of "no fake data":** applies to **runtime** behavior. Test doubles are allowed only in `tests/` (Section 30). Dry-run is not "fake data": it uses real market data and clearly labeled `THEORETICAL` outputs.
- Timezone-aware datetimes only (UTC internally); `Decimal` for money/lot math with explicit rounding rules; no float equality; no bare `except`; no swallowed errors; no blocking calls on the asyncio loop; no module-level mutable globals; bounded retries with backoff + jitter; timeouts on every external call; small pure functions for calculations; explicit units in names (`_points`, `_price`, `_ccy`, `_ms`).
- Tools: `ruff`, `mypy --strict` (trading/risk/mt5), `eslint`, `tsc --noEmit`, `pre-commit`; pinned dependency versions; conventional, small commits.
- Where a feature genuinely cannot be implemented yet, raise `NotImplementedError` with a clear message and list it in the phase report — do not silently stub it as "working".

---

## 44. FIRST TASK

Before implementing the entire application, inspect the current development environment.

Check:

- Python version
- Node version
- npm version
- MT5 installation
- MetaTrader5 Python package
- available project directory

Then create the project structure.

After that, implement Phase 1 and Phase 2 only.

Run tests.

Then implement the MT5 demo connection.

Do not jump directly into the aggressive XAUUSD strategy.

The final goal is:

```
USER
  ↓
CUSTOM TRADING TERMINAL
  ↓
TRADING ENGINE
  ↓
MT5 ADAPTER
  ↓
MT5 DESKTOP TERMINAL
  ↓
BROKER DEMO SERVER
  ↓
XAUUSD DEMO POSITIONS
  ↓
REAL MT5 P/L
  ↓
CUSTOM TERMINAL
```

Everything displayed as an actual trading result must originate from the connected MT5 demo account.

Build the system incrementally, test every layer, and report exactly what works, what fails, and what remains.

**[ADD] First-task specifics**

1. Run and paste output of: OS/version, `python --version`, `pip --version`, `node --version`, `npm --version`, whether `terminal64.exe` exists and is running, `pip show MetaTrader5`, free disk, working directory. Create `scripts/preflight.py` that automates this and exits non-zero on blockers.
2. **If the OS is not Windows, stop MT5-dependent work**, explain, and continue only with OS-independent parts (config, DB, risk logic, strategy, sizing, frontend) built against the `TradingGateway` interface — with tests using test-only fakes.
3. Create the project structure (Section 35), CI skeleton, `docs/PROGRESS.md`, `docs/DECISIONS.md`.
4. Implement Phase 1 and Phase 2 (including the Phase 2 minimal guardrails from Section 36), run tests, produce the **PHASE REPORT**, and **wait for approval**.
5. Then Phase 3 (the user provides `.env` locally; the agent does not request secrets in chat).

---

# NEW CROSS-CUTTING SECTIONS **[ADD]**

## 45. CONCURRENCY & EXECUTION MODEL

- **Threads/loops:** (a) MT5 worker thread — the *only* thread that calls MT5; (b) asyncio loop — API, WebSocket, DB, event bus; (c) trading-engine loop — single consumer that processes ticks/commands **sequentially** through a command queue.
- **Commands** from the API (start, pause, close-all, modify…) are enqueued to the engine loop, not executed in the request handler, so they can't race the strategy tick. Kill switch has a **priority lane** that pre-empts the queue.
- **One order in flight per basket**, plus a global order rate limiter (protects against `TOO_MANY_REQUESTS` 10024) and MT5 call throttling.
- **Locks:** a per-basket lock and a state-machine lock; never hold a lock across a network/MT5 wait longer than the call timeout; no lock-ordering cycles (document order).
- **No shared mutable state** across threads; use immutable snapshots (frozen dataclasses/Pydantic models) on the event bus.
- Exceptions in any loop are caught at the top, logged, raise an alert, and (for the engine loop) move the system to `ERROR` and block entries — a crashed loop must never leave the bot "running but blind".
- A **watchdog task** monitors loop heartbeats (engine, risk, reconciliation, market data); a stalled heartbeat blocks entries and alerts.

## 46. TIME HANDLING

- MT5 timestamps (ticks, positions, deals, rates) are **broker server time encoded as if UTC**, not real UTC. Determine the server offset at startup (e.g. compare latest tick time to UTC now, verified against a known offset in config) and re-check periodically, including around DST changes.
- Store all times in **UTC**; keep the raw server time in a separate column for audit. Convert at the edges only. UI can toggle UTC/server/local.
- Also detect **local PC clock skew** (e.g. NTP check); warn if large — it affects staleness and cooldowns.
- Cooldowns and rate limits use a **monotonic clock**, not wall time.
- Day boundaries (daily loss, today's P/L) use the configured trading-day boundary (Section 13). Tests must cover DST changes, day rollover, week rollover, and swap-triple-day (Wednesday for most gold CFDs — read from `symbol_info.swap_rollover3days`).
- Sessions/market hours come from MT5 session info, not hardcoded UTC assumptions.

## 47. HEDGING vs NETTING ACCOUNTS

- Read `account_info().margin_mode`: `RETAIL_HEDGING` (multiple independent positions per symbol — required for grid/basket with separate tickets and for BOTH-direction baskets), `RETAIL_NETTING` and `EXCHANGE` (one net position per symbol — opposite orders reduce/flip, individual tickets don't exist).
- **Grid/basket strategy and `direction = BOTH` are refused on non-hedging accounts** with a clear message. If the user still wants to test single-direction on a netting account, that needs an explicit, documented "netted position" basket model — out of scope for V1 unless the user requests it.
- Show margin mode in the UI header and pre-flight report; include tests for both.

## 48. FAILURE-MODE MATRIX (must be implemented and tested)

| Failure | Detection | Automatic response | Operator signal |
|---|---|---|---|
| MT5 terminal closed/crashed | `terminal_info` fails / `None` | Block entries, `ConnectionState=DISCONNECTED`, reconnect with backoff, reconcile on recovery | CRITICAL alert if positions open |
| Internet/broker link down | `terminal_info().connected == False`, stale ticks | Block entries; positions rely on broker-side SL | Alert + banner |
| Algo trading toggled off | `trade_allowed == False`, retcode 10027 | Block entries, state `ERROR`/`PAUSED` | Alert with fix |
| Login/account switched | login/server mismatch | Block entries, `ERROR` | CRITICAL alert |
| Account becomes non-demo | trade_mode check | Refuse orders, `ERROR` | CRITICAL alert |
| Order rejected | retcode | No blind retry; classify; maybe bounded retry for transient | Rejected-order card |
| Order outcome unknown | `None`/timeout | Freeze basket, query MT5 by magic/comment, resolve | Warning until resolved |
| Partial fill | `DONE_PARTIAL` | Track actual volume; decide on remainder per policy | Log + card |
| Stale/frozen ticks | age/frozen detector | Block entries | Warning badge |
| Spread spike | spread > max | Block entries; existing exits still evaluated | Warning |
| Margin level low | risk manager | Block entries → optional close per config | Alert |
| Stop-out by broker | deal reason `SO`, positions vanish | Reconcile, record reason, stop strategy, latch risk event | CRITICAL alert |
| Position closed manually | reconciliation | Update basket, no instant re-entry | Info log |
| Unknown/foreign position | reconciliation | Classify; never manage foreign | Warning |
| Duplicate level detected | key collision | Freeze basket entries | Alert |
| DB unavailable | write errors | Continue safety-critical actions, buffer events, retry | Alert |
| Engine/loop crash | watchdog/top-level catch | Block entries, `ERROR` | CRITICAL alert |
| Two instances | instance lock | Second exits immediately | Message |
| Process killed | — | On restart: persisted state, adopt positions, reconcile | Startup report |
| Clock skew/offset change | startup/periodic check | Block entries until resolved | Warning |
| Weekend/market close with open basket | session data | Per config: flatten before close or protective SL only | Alert |
| Close-all partially fails | verification step | Bounded retries, escalate, keep `CLOSING` | CRITICAL alert |

## 49. MT5 RETCODE & ERROR HANDLING TABLE

Implement in `retcodes.py` (verify each value against the official MT5 documentation at implementation time; the numbers below are the commonly used ones):

| Code | Name | Meaning | Policy |
|---|---|---|---|
| 10004 | REQUOTE | Price changed | Retry ≤ N with fresh price if within deviation policy |
| 10006 | REJECT | Request rejected | No blind retry; log; alert on repeats |
| 10007 | CANCEL | Canceled by trader | Log |
| 10008 | PLACED | Pending order placed | Verify order exists |
| 10009 | DONE | Executed | Verify via positions/deals |
| 10010 | DONE_PARTIAL | Partly executed | Track actual volume; policy for remainder |
| 10013 | INVALID | Invalid request | Bug/config problem: block entries, alert |
| 10014 | INVALID_VOLUME | Bad volume | Never auto-retry; fix sizing |
| 10015 | INVALID_PRICE | Bad price | Refresh price; bounded retry |
| 10016 | INVALID_STOPS | SL/TP too close/invalid | Recompute vs `stops_level`; no blind retry |
| 10017 | TRADE_DISABLED | Trading disabled | Block entries; alert |
| 10018 | MARKET_CLOSED | Market closed | Block entries; no alert storm |
| 10019 | NO_MONEY | Insufficient funds | Block entries; risk event |
| 10020 | PRICE_CHANGED | Prices changed | Bounded retry |
| 10021 | PRICE_OFF | No quotes | Block; retry later |
| 10024 | TOO_MANY_REQUESTS | Rate limited | Back off |
| 10025 | NO_CHANGES | Nothing to modify | Treat as no-op |
| 10027 | CLIENT_DISABLES_AT | Algo trading disabled in terminal | Block; instruct user |
| 10028 | LOCKED | Locked for processing | Retry later |
| 10029 | FROZEN | Order/position frozen | Wait; alert |
| 10030 | INVALID_FILL | Unsupported filling mode | Re-detect filling mode; bounded retry |
| 10031 | CONNECTION | No connection to server | Reconnect flow |
| 10032 | ONLY_REAL | Only live accounts allowed | Treat as configuration error |
| 10033/10034 | LIMIT_ORDERS / LIMIT_VOLUME | Broker limit hit | Block; alert |
| 10036 | POSITION_CLOSED | Position already closed | Success-if-verified for close |

Python API errors from `mt5.last_error()`: `1` OK, `-1` fail, `-2` invalid params, `-4` not found, `-6` authorization failed, `-7` unsupported, `-8` auto-trading disabled, `-10000…-10005` internal/IPC (`-10003` IPC initialize failed, `-10004` no connection, `-10005` timeout). Each maps to a structured exception, a human-readable explanation, and a suggested fix shown in the UI.

## 50. INDEPENDENT PROTECTIVE LAYERS (what protects you if the bot dies)

A software basket SL is worthless if the PC, the Python process, or the internet goes down. Therefore:

1. **Broker-side protective SL (mandatory in DEMO EXECUTION unless explicitly waived and logged):** every position gets a wide "catastrophic" SL (`protective_sl_points` in config, sized against the worst-case preview). Basket SL/TP managed by the bot stays the primary logic; the server-side SL is the backstop. When basket composition changes, protective levels are re-evaluated and kept consistent.
2. **Absolute account-level guards** in the Risk Manager (max drawdown/daily loss/margin level) run in a separate loop from the strategy.
3. **Optional watchdog EA (MQL5, phase after Phase 9):** a tiny Expert Advisor inside the terminal that reads a heartbeat (global variable or file) written by the Python bot; if the heartbeat is lost for N seconds *and* limits are exceeded (or the kill flag is set), it closes bot-magic positions. It runs terminal-side, so it survives a Python crash (not a full PC/terminal outage). Provide source, install steps, and tests; clearly document limits.
4. **Deployment guidance in RUNBOOK:** run on a stable machine/VPS, disable sleep/hibernate, auto-restart policy for the backend, MT5 auto-login, alert on heartbeat loss.

## 51. OUT OF SCOPE FOR V1 / LIVE-TRADING GATE

Out of scope: live accounts, multi-account, multiple brokers, non-XAUUSD instruments, netting-account grid model, mobile app, social/copy-trading features, ML/AI signal generation, cloud-hosted control panel.

A future Version 2 that considers live trading must **start from a written proposal** and meet, at minimum: independent security review, weeks of demo evidence with reconciled results, hard capital limits, separate live credentials/config profile, physical kill-switch procedure, legal/regulatory review by the user. **Nothing in V1 code may pave a silent path to that** (no hidden flags, no commented-out live code).

## 52. PHASE REPORT TEMPLATE & DEFINITION OF DONE

At the end of every phase output exactly:

```
PHASE REPORT — Phase N: <name>
1. What was built (files/modules)
2. Commands run + ACTUAL output (pytest summary, preflight, lint, mypy)
3. What works (each item mapped to a Section 42 checkbox + evidence)
4. What FAILS or is flaky (be specific)
5. What was NOT done / deferred (and why)
6. Decisions made (added to DECISIONS.md) + assumptions needing user confirmation
7. Risks / safety observations discovered
8. Exact next step + what I need from the user (approval, .env set locally, etc.)
```

**Definition of Done for the whole project:** every Section 42 box (original + added) is checked **with evidence**; all automated gates pass; integration tests pass on a real demo account; a full dry-run → demo-execution → basket TP → basket SL → kill-switch → restart-recovery rehearsal has been executed and documented; docs and README match the shipped behavior; the risk disclosure is visible in the app and docs.

---

**Risk disclosure (must appear in README, in the app's Settings page, and in RISK_MANAGEMENT.md):**
*This software is for educational/experimental use on demo accounts. It does not provide financial advice and makes no claim of profitability. Grid, averaging-down, and multiplier strategies can produce very large losses in a single adverse move. Demo-account results (fills, slippage, liquidity) do not reflect live-market conditions. The author/agent cannot guarantee correct behavior on every broker; verify everything in the MT5 terminal itself.*
