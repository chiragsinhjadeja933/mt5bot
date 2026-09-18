# Risk Management & Safety Specifications

> [!CAUTION]
> **PROMINENT RISK DISCLOSURE (Section 0.4 / 52)**
> This software is designed strictly for educational and experimental evaluation on **MetaTrader 5 Demo Accounts**. It does not provide financial advice and makes no claim of profitability. Grid, averaging-down, and multiplier strategies can produce devastating account wipeouts during a single sustained adverse trend. Demo results (execution latency, simulated slippage, infinite liquidity) do not reflect real market conditions. Always verify positions directly in the desktop MT5 terminal.

---

## 1. Hard Safety Limits

The Risk Manager (`app/risk/manager.py`) operates as a mandatory gateway before any order reaches MT5.

| Safety Check | Default Value | Action on Breach |
| :--- | :--- | :--- |
| **Demo Account Verification** | Enforced | Immediate rejection if account is REAL or CONTEST |
| **Hedging Account Mode** | Enforced | Netting accounts rejected (cannot support grid baskets) |
| **Max Daily Loss** | \$500.00 | Trading halts for the calendar day; transitions to PAUSED |
| **Max Drawdown Limit** | 20.0% of peak equity | Trading halts; requires explicit manual review |
| **Max Spread Filter** | 60 points | Entries suppressed until spread narrows |
| **Stale Data Timeout** | 5.0 seconds | Market data marked invalid; order pipeline fails closed |
| **Absolute Max Volume** | 1.00 lot | Clamps volume; rejects orders exceeding cap |

---

## 2. Latching Limits & Manual Reset Procedure

Certain catastrophic risk breaches latch permanently:
- If **Max Daily Loss** or **Max Total Drawdown** is triggered, the system latches into `PAUSED` or `EMERGENCY_STOP`.
- The bot **will not resume automatically** when the next tick arrives.
- To resume trading after a latched breach:
  1. The user must inspect open positions in MT5.
  2. Resolve the underlying market situation.
  3. Send an authenticated `POST /api/trading/reset-emergency` containing `{"confirmation_token": "RESET"}`.

---

## 3. Defense Against Market Closure & Disconnections

- **Fails Closed:** If tick data stops arriving for more than `stale_data_timeout_seconds` (e.g. over weekends or during network blips), the strategy skips tick processing and blocks new entries.
- **Exits Allowed While Paused:** In the `PAUSED` state, all `ENTRY` orders are prohibited, but `REDUCE` and basket closing orders remain fully permitted to allow de-risking.
