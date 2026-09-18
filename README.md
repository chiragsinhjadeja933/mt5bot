# MT5 Demo Trading Terminal + Automated XAUUSD Trading Bot

[![CI Pipeline](https://img.shields.io/badge/CI-Passing-brightgreen)](.github/workflows/ci.yml)
[![Platform](https://img.shields.io/badge/Platform-Windows%20Native-blue)]()
[![License](https://img.shields.io/badge/License-MIT-green)]()

> [!CAUTION]
> **PROMINENT RISK DISCLOSURE (Section 0.4 / 52)**
> *This software is for educational/experimental use on demo accounts. It does not provide financial advice and makes no claim of profitability. Grid, averaging-down, and multiplier strategies can produce very large losses in a single adverse move. Demo-account results (fills, slippage, liquidity) do not reflect live-market conditions. The author/agent cannot guarantee correct behavior on every broker; verify everything in the MT5 terminal itself.*

---

## 1. What the System Does

The **MT5 Demo Trading Terminal** is a high-performance, production-quality trading application engineered specifically for MetaTrader 5 demo accounts. It features:
- **Centralized Dashboard UI:** Real-time account equity, balance, margin, active positions, floating P/L, and one-click controls.
- **Automated XAUUSD Grid Strategy Engine:** Deterministic, configurable adverse (averaging-down) or favorable (pyramid) grid engine.
- **Basket Management:** Aggregated weighted-average entry, floating gross/net PnL calculation, and synchronized basket take-profit / stop-loss execution.
- **Independent Risk Manager:** Enforces hard circuit breakers (daily loss limit, max drawdown, spread spikes, stale data timeout).
- **Dual Execution Modes:** Pure virtual `DRY_RUN` mode and live `DEMO_EXECUTION`.
- **Two-Step Start & Emergency Kill Switch:** Prevents accidental activation; provides instant position closing with persistent state locking.

---

## 2. Platform Reality & Prerequisites

> [!IMPORTANT]
> **Windows Native Execution Required (Section 0.2)**
> The official `MetaTrader5` Python library interacts with `terminal64.exe` via Windows shared memory/IPC channels in the same desktop user session. It **cannot run inside a Linux Docker container**.
> The backend runs **natively on Windows** (Windows 10/11 or Windows Server VPS).

### Minimum Requirements:
- **Operating System:** Windows 10, 11, or Windows Server 2019+
- **Python:** Version 3.10 to 3.13 (64-bit)
- **Node.js:** Version 18.0+ & npm 9+
- **MetaTrader 5:** Installed desktop client (`terminal64.exe`) logged into a **Demo Account** (Hedging mode required)

---

## 3. Quick Start Guide

### Step 1: Preflight Verification
Verify your system environment and dependencies:
```powershell
cd "d:\mt5 bot new\mt5-trading-terminal"
python scripts/preflight.py
```

### Step 2: Configure Environment Variables
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```
Edit `.env` with your local settings (credentials stay local on your PC):
```ini
MT5_PATH="C:\Program Files\MetaTrader 5\terminal64.exe"
MT5_LOGIN=12345678
MT5_PASSWORD="your_demo_password"
MT5_SERVER="MetaQuotes-Demo"
API_TOKEN="your_secure_random_api_token"
```

### Step 3: Start Backend
```powershell
.\scripts\start_backend.ps1
# or manually:
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

### Step 4: Start Frontend
In a separate terminal window:
```powershell
.\scripts\start_frontend.ps1
# or manually:
cd frontend
npm run dev
```
Open your browser at `http://localhost:3000`.

---

## 4. Operational Workflows

### How to Run the Connection Diagnostic Test
1. Navigate to the **Connection Test** page (`http://localhost:3000/connection-test`).
2. Click **Run Diagnostic**. The system executes:
   - MT5 terminal detection
   - Demo login verification
   - Symbol specification discovery (`XAUUSD`)
   - Tick streaming verification
   - Micro 0.01 lot test BUY & immediate close (verifying retcode 10009).

### How to Enable Dry Run vs Demo Execution
- By default, the terminal boots in `DRY_RUN` mode. Strategy orders produce virtual simulated fills using live tick quotes.
- To switch to `DEMO_EXECUTION`:
  1. Open the **Strategy** page.
  2. In the Execution Mode switcher, select **DEMO EXECUTION**.
  3. Type the exact confirmation token: `DEMO EXECUTION`.

### How to Start the Strategy
1. Configure your grid parameters (distance points, initial lot, basket TP).
2. Click **Start Bot**.
3. A confirmation dialog appears. Type `START DEMO` to confirm.

### How to Stop & Emergency Stop
- **Pause:** Halts new entries while continuing to manage exits for open baskets.
- **Stop:** Gracefully stops trading.
- **Emergency Stop (Kill Switch):** Instantly terminates all bot activity, closes all open bot positions via market orders, and latches into `EMERGENCY_STOP`.
- **Reset:** To restore the bot after an emergency stop, click **Reset** and type `RESET`.

---

## 5. Troubleshooting Matrix

| Symptom | Cause | Resolution |
| :--- | :--- | :--- |
| **`initialize() failed: -10003`** | MT5 IPC connection failed | Ensure `terminal64.exe` is running under the same Windows user account; check `MT5_PATH` in `.env`. |
| **Authorization failed (`-6`)** | Incorrect login, password, or broker server | Verify demo credentials in desktop MT5 first, then update `.env`. |
| **Auto-trading disabled (`-8`, `10027`)** | Terminal Algo Trading toggle is OFF | In MT5 desktop menu, click the **"Algo Trading"** button on the top toolbar so it turns green. |
| **Symbol Not Found (`XAUUSD`)** | Broker uses an alias (e.g. `XAUUSDm`, `GOLD`) | Add your broker's specific gold symbol name in `.env` (`MT5_SYMBOL="XAUUSDm"`). |
| **Market Closed (`10018`)** | Weekend or broker holiday | Wait for market open (Sunday 5:00 PM EST). |
| **Invalid Stops (`10016`)** | SL/TP is closer than broker `stops_level` | Increase `protective_sl_points` in strategy settings. |
| **Unsupported Filling Mode (`10030`)** | Broker does not accept requested filling mode | The system automatically selects broker-supported mode (`FOK`, `IOC`, or `RETURN`). |
| **Netting Account Detected** | Broker account is netting rather than hedging | Create a **Hedging** demo account in MT5 (`Tools -> Options -> Accounts -> Open an Account -> Hedging`). |
| **Port Already in Use (`8000`)** | Previous uvicorn instance still running | Terminate old Python process or use `Stop-Process -Name python`. |
| **Another instance is running (PID ...)** | Lockfile `mt5terminal.lock` active | Terminate duplicate bot instance; delete `mt5terminal.lock` if stale. |

---

## 6. Architecture & Documentation Directory

For in-depth technical documentation, consult the `docs/` folder:
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): System architecture, component layers, sequence diagrams.
- [docs/TRADING_ENGINE.md](docs/TRADING_ENGINE.md): Detailed mechanics of grid logic, sizing engine, and basket management.
- [docs/RISK_MANAGEMENT.md](docs/RISK_MANAGEMENT.md): Risk rules, limits, latching behavior, and safety controls.
- [docs/MT5_INTEGRATION.md](docs/MT5_INTEGRATION.md): Native Windows IPC, retcodes, and error handling.
- [docs/RUNBOOK.md](docs/RUNBOOK.md): Operator runbook for disconnects, crashes, and emergency procedures.
- [docs/SECURITY.md](docs/SECURITY.md): Network boundary, Bearer auth, token validation, secret handling.
- [docs/TESTING.md](docs/TESTING.md): Testing strategies, test suites, and instructions.
- [docs/PROGRESS.md](docs/PROGRESS.md): Section 42 Acceptance Criteria verification checklist.
- [docs/DECISIONS.md](docs/DECISIONS.md): Architectural Decision Records (ADR).
