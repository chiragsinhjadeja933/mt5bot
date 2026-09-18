# MetaTrader 5 Integration Specifications

This document describes the native integration between Python and the desktop MetaTrader 5 terminal (`terminal64.exe`).

---

## 1. Operating Environment & IPC

The official `MetaTrader5` Python library interacts with the running MT5 terminal via Windows-specific shared memory / IPC channels.

- **OS Requirement:** Windows 10/11 or Windows Server.
- **Session Requirement:** The Python backend must run under the same Windows interactive desktop user session as `terminal64.exe`.
- **Concurrency:** Process-local state requires running **one uvicorn worker only**. All MT5 API calls are dispatched sequentially through a dedicated worker thread to maintain thread safety.

---

## 2. Initialization & Connection Lifecycle

1. **Detection:** Checks whether `terminal64.exe` is running; if not, attempts launching from `MT5_PATH`.
2. **Initialization:**
   ```python
   mt5.initialize(path=settings.mt5_path, login=login, password=password, server=server)
   ```
3. **Safety Verification:**
   - Verify `account_info.trade_mode == ACCOUNT_TRADE_MODE_DEMO`.
   - Verify `account_info.trade_allowed == True` (Algo Trading enabled).
   - Verify `account_info.margin_mode == ACCOUNT_MARGIN_MODE_RETAIL_HEDGING`.

---

## 3. Symbol Discovery & Aliases

Brokers frequently use custom suffixes for gold symbols. `app/mt5/symbols.py` attempts:
1. Exact match for configured symbol (e.g. `XAUUSD`).
2. Common broker aliases: `XAUUSDm`, `XAUUSD.a`, `XAUUSDraw`, `GOLD`, `GOLDm`.
3. Selects the symbol in MT5 MarketWatch via `mt5.symbol_select(symbol, True)`.
4. Reads and caches:
   - `point`, `digits`, `spread`
   - `volume_min`, `volume_max`, `volume_step`
   - `filling_mode` (`ORDER_FILLING_FOK`, `ORDER_FILLING_IOC`, `ORDER_FILLING_RETURN`)

---

## 4. Retcode Mapping & Error Handling

All broker responses from `mt5.order_send()` are parsed through `app/mt5/retcodes.py`:

| Retcode | Identifier | Description | Policy |
| :--- | :--- | :--- | :--- |
| `10009` | `TRADE_RETCODE_DONE` | Order executed successfully | Success |
| `10004` | `TRADE_RETCODE_REQUOTE` | Price changed | Transient: retry with updated price |
| `10018` | `TRADE_RETCODE_MARKET_CLOSED` | Market is closed | Non-retryable: suppress alerts |
| `10016` | `TRADE_RETCODE_INVALID_STOPS` | Stop Loss / TP invalid | Configuration error: log and halt |
| `10027` | `TRADE_RETCODE_AUTOTRADING_DISABLED` | Terminal algo trading button off | Fatal: instruct user to enable algo trading |
| `10030` | `TRADE_RETCODE_UNSUPPORTED_FILLING_MODE` | Incompatible filling mode | Auto-fallback to broker supported mode |
