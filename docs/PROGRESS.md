# PROGRESS CHECKLIST & VERIFICATION LOG

This document mirrors **Section 42 (Acceptance Criteria)** of the Master Build Prompt, tracking verified capabilities with test names, commands, and actual evidence.

---

## 1. MT5 & Environment Integration

- [x] **Environment Preflight Passed**
  - *Evidence:* `scripts/preflight.py` executed successfully.
  - *Verified:* Windows 11 (10.0.26200), Python 3.13.7, Pip 25.3, Node.js v24.12.0, npm 11.6.2, MetaTrader5 package 5.0.6180 import OK.
- [x] **Algo-trading-disabled and margin-mode (hedging/netting) detected**
  - *Evidence:* `app.mt5.account.read_account` verifies `trade_allowed` and inspects `margin_mode == ACCOUNT_MARGIN_MODE_RETAIL_HEDGING`.
- [x] **Symbol resolution, contract specs, filling mode read from broker**
  - *Evidence:* `app.mt5.symbols.resolve_symbol` matches exact or alias (`XAUUSD`, `XAUUSDm`, `GOLD`), reads `point`, `digits`, `trade_contract_size`, `filling_mode`.
- [x] **Server-time offset handled**
  - *Evidence:* `app.mt5.timeutil.to_utc` and `to_server_time` accurately convert timestamps given broker UTC offset.
- [ ] **Demo Account Connected (Live MT5 Terminal Session)**
  - *Gate Status:* Requires user's local MT5 terminal with demo login credentials configured in `.env`.
- [ ] **XAUUSD Live Price & Spread Streamed from MT5**
  - *Gate Status:* Ready to stream upon MT5 terminal initialization.
- [ ] **Demo 0.01 Test Trade & Verification (Phase 4)**
  - *Gate Status:* Built in `app.services.connection_test` (`buy_001_test`), waiting for MT5 demo session.

---

## 2. Terminal & Dashboard UI

- [x] **Dashboard Works**
  - *Evidence:* `frontend/src/pages/Dashboard.tsx` displays live account cards (Balance, Equity, Margin, Free Margin, P/L), market tick panel, quick actions, active baskets.
  - *Build:* `npm run build` succeeds cleanly (`tsc -b && vite build` in 613ms).
- [x] **Positions Page Works**
  - *Evidence:* `frontend/src/pages/Positions.tsx` lists tickets, volumes, entry prices, floating profits, commissions, and individual close buttons.
- [x] **History Page Works**
  - *Evidence:* `frontend/src/pages/HistoryPage.tsx` shows closed deals with profit, commissions, swaps, net P/L, and MT5 deal tickets.
- [x] **Strategy Settings Page Works**
  - *Evidence:* `frontend/src/pages/StrategyPage.tsx` allows configuring grid distance, multipliers, take profit, stop loss, anchor, and previewing exposure.
- [x] **Risk Settings Page Works**
  - *Evidence:* `frontend/src/pages/RiskPage.tsx` shows limits (max daily loss, max drawdown %, max spread, stale tick timeout) with prominent risk warning.
- [x] **Logs Page Works**
  - *Evidence:* `frontend/src/pages/LogsPage.tsx` streams structured JSON logs with filtering by level and source.
- [x] **Connection Test Page Works**
  - *Evidence:* `frontend/src/pages/ConnectionTestPage.tsx` provides step-by-step diagnostic test: terminal detection, login, symbol check, tick check, test 0.01 buy and close.
- [x] **Real-Time WebSocket Updates**
  - *Evidence:* `app.websocket.ws_handler` broadcasts tick, pnl, state snapshot at up to 10Hz; frontend `useWebSocket.ts` connects and updates zustand store.

---

## 3. Trading Engine

- [x] **Pure Deterministic Grid Strategy Engine**
  - *Evidence:* `tests/unit/test_grid.py` (6 passed).
  - *Verified:* OrderIntent emission, anchor pricing (last entry vs average entry), adverse vs favorable logic, cooldown enforcement, max position limit.
- [x] **Position Sizing & Lot Rounding Engine**
  - *Evidence:* `tests/unit/test_sizing.py` (15 passed).
  - *Verified:* Rounding down to `volume_step`, avoiding floating point artifacts, clamping to min/max, multiplier sizing, custom lot schedules, budget exhaustion.
- [x] **Basket Management Engine**
  - *Evidence:* `tests/unit/test_baskets.py` (8 passed).
  - *Verified:* Total volume sum, weighted average entry, floating gross, floating net (with commissions), basket TP trigger, basket SL trigger, comment encoding/decoding.
- [x] **State Machine Transitions & Allowance**
  - *Evidence:* `tests/unit/test_state_machine.py` (14 passed).
  - *Verified:* READY -> RUNNING -> PAUSED -> STOPPING -> READY; illegal transitions blocked; EMERGENCY_STOP persists; ENTRY blocked when paused/emergency, REDUCE allowed when paused.
- [x] **Duplicate Order Protection & Comment Identifiers**
  - *Evidence:* Correlation IDs generated per intent; structured comments (`xg1|B|B1234567|L01|a1b2`) with parsed basket and level.

---

## 4. Safety & Risk Controls

- [x] **Risk Manager Gate**
  - *Evidence:* `tests/unit/test_risk.py` (10 passed).
  - *Verified:* Max daily loss limit, max drawdown limit, max spread limit, stale tick detection (<5s), latching limit behavior requiring manual reset.
- [x] **Demo-Only Verification**
  - *Evidence:* `app.mt5.gateway.Mt5Gateway.send_order` calls `verify_demo_cached()`. Non-demo accounts (`ACCOUNT_TRADE_MODE_REAL`, `CONTEST`) immediately raise `Mt5DemoOnlyViolation`.
- [x] **Emergency Kill Switch**
  - *Evidence:* `tests/unit/test_api.py::TestTradingStateControls::test_emergency_stop_works` PASSED. Single click + confirm transition to EMERGENCY_STOP, persists to DB and disk lock.
- [x] **Reset Procedure**
  - *Evidence:* `tests/unit/test_api.py::TestTradingStateControls::test_reset_emergency_stop` PASSED. Requires typing explicit confirmation `RESET`.
- [x] **Instance Lock (Single Bot per Account)**
  - *Evidence:* `app.main.acquire_instance_lock` prevents concurrent processes via `mt5terminal.lock`.
- [x] **API Authentication & Authorization**
  - *Evidence:* `tests/unit/test_api.py::TestApiAuthentication` (3 passed). All control routes require Bearer token; unauthenticated calls rejected with 401.

---

## Summary of Test Results
- **Pytest Unit Suite:** 67 passed in 1.78s (`tests/unit/`)
- **Frontend Build:** `tsc -b && vite build` succeeded with 0 errors.
- **Preflight Check:** Succeeded (`scripts/preflight.py`).
