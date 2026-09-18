# Testing Strategy & Verification Guide

This document outlines the testing architecture, test suites, and execution instructions for the trading terminal.

---

## 1. Test Architecture

The test suite is organized into three distinct tiers:

1. **Unit Tests (`backend/tests/unit/`):**
   - Pure, deterministic, zero MT5 dependencies.
   - Run in milliseconds.
   - Includes:
     - `test_sizing.py`: Lot rounding down, min/max clamping, multiplier calculations, step alignment.
     - `test_risk.py`: Daily loss limit, max drawdown, spread spikes, stale data timeout, latching state.
     - `test_state_machine.py`: Legal vs illegal transitions, emergency stop persistence, order allowance by state.
     - `test_grid.py`: Injected clock, adverse vs favorable grid triggers, cooldown, max positions.
     - `test_baskets.py`: Weighted average entry, gross and net PnL, basket TP, basket SL, comment encoding.
     - `test_api.py`: FastAPI endpoint security, token authentication, typed confirmation start/reset.
2. **Integration Tests (`backend/tests/integration/`):**
   - Validates multi-component flows (e.g. gateway + state machine + database persistence).
3. **Environment Preflight (`scripts/preflight.py`):**
   - Verifies system requirements, OS platform, Python version, MetaTrader5 module, Node.js, and npm.

---

## 2. Running Automated Tests

### Run Backend Tests:
```powershell
cd "d:\mt5 bot new\mt5-trading-terminal\backend"
python -m pytest tests/unit/ -v --tb=short
```

### Run Frontend Typecheck & Build:
```powershell
cd "d:\mt5 bot new\mt5-trading-terminal\frontend"
npm run build
```

### Run Environment Preflight:
```powershell
cd "d:\mt5 bot new\mt5-trading-terminal"
python scripts/preflight.py
```
