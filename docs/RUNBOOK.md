# Incident Runbook & Operational Procedures

This runbook specifies step-by-step procedures for operators dealing with unexpected system states, crashes, or disconnects.

---

## 1. MT5 Terminal Disconnected with Open Positions

### Symptoms
- UI indicates `ConnectionState: DISCONNECTED` or `ERROR`.
- Existing basket positions remain open on the broker side.

### Action Plan
1. **Do not panic:** If protective Stop Losses were configured, the broker server safeguards each open position.
2. **Open Desktop MT5:** Check the MT5 terminal window directly.
3. If MT5 terminal is frozen, terminate `terminal64.exe` via Task Manager and re-launch it.
4. If the internet connection dropped, wait for network restoration.
5. Once MT5 reconnects, restart the backend terminal. The reconciliation engine will detect and adopt existing open positions.

---

## 2. Emergency Kill Switch (Manual Emergency Procedure)

If the web UI cannot be accessed or fails to close open positions:

1. **Terminal One-Click Close:**
   - Switch to the desktop MT5 terminal.
   - Open the **Trade** tab at the bottom.
   - Click the **X** button on each position to close manually.
2. **Global Variable Kill:**
   - If `Watchdog.mq5` EA is active, in MT5 press `F3` (Global Variables).
   - Add/Set `BOT_KILL` = `1.0`.
   - The Watchdog EA will close all bot positions within 1 second.
3. **Emergency API Command via curl:**
   ```bash
   curl -X POST http://127.0.0.1:8000/api/trading/emergency-stop \
        -H "Authorization: Bearer YOUR_API_TOKEN"
   ```

---

## 3. Restarting After a Crash

1. **Verify Process Status:**
   Ensure no hung Python process holds `mt5terminal.lock`. If necessary, remove the lockfile after terminating orphan processes:
   ```powershell
   Remove-Item mt5terminal.lock -ErrorAction SilentlyContinue
   ```
2. **Launch Backend:**
   ```powershell
   .\scripts\start_backend.ps1
   ```
3. **Check Reconciliation:**
   - Review `/api/positions` or the Positions page.
   - Confirm that all existing tickets were re-adopted with their original basket IDs.
