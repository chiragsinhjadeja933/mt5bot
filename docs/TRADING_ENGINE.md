# Trading Engine Specifications

The Trading Engine comprises the Strategy Engine, Position Sizing Engine, and Basket Management Engine.

---

## 1. Grid Strategy Engine (`app/trading/grid.py`)

The grid engine is pure and deterministic. It processes market and portfolio snapshots without interacting with MT5 directly.

### Operational Modes
1. **Adverse Grid Mode (Averaging Down):**
   - **BUY Basket:** Adds new long positions as the market moves downward against the basket.
   - **SELL Basket:** Adds new short positions as the market moves upward against the basket.
   - *Risk Warning:* Highly dangerous during sustained trends. Requires strict basket stop-loss.
2. **Favorable Grid Mode (Pyramiding):**
   - Adds new positions only as the trade moves in profit.

### Anchor Reference Models
- `last_entry`: The distance for the next grid leg is calculated from the price of the most recent fill (`state.last_entry_price`).
- `average_entry`: The distance is measured from the volume-weighted average price (`portfolio.avg_entry_price`).

---

## 2. Position Sizing Engine (`app/trading/sizing.py`)

Lot calculations must adhere to strict mathematical precision to prevent order rejection:

1. **Volume Rounding Down:**
   - Volume is rounded **strictly down** (`ROUND_DOWN`) to the nearest broker `volume_step`:
     $$\text{effective\_lots} = \lfloor \frac{\text{requested\_lots}}{\text{step}} \rfloor \times \text{step}$$
   - Prevents requesting lots exceeding user balance or margin budgets.
2. **Clamping:**
   - Effective volume is clamped between broker `volume_min` and `volume_max`.
3. **Lot Multipliers:**
   - Multiplier modes (e.g. 1.2x, 1.5x) are disabled by default and require setting `allow_multiplier: true` to prevent accidental martingale configuration.
   - Total lots across all open levels are capped at `max_total_lots`.

---

## 3. Basket Management Engine (`app/trading/baskets.py`)

A basket represents all positions sharing the same magic number and `basket_id`.

### P/L Metrics
- **Floating Gross:** $\sum \text{position.profit} + \sum \text{swap}$
- **Floating Net:** $\text{Floating Gross} + \sum \text{entry\_commission}$
- **Weighted Average Entry:**
  $$\bar{P}_{\text{entry}} = \frac{\sum (V_i \times P_i)}{\sum V_i}$$

### Exits & Protections
- **Basket Take Profit (`basket_tp`):** When basket net P/L reaches the currency target, an exit signal closes all legs simultaneously.
- **Basket Stop Loss (`basket_sl`):** Hard account equity backstop to terminate the basket if drawdown exceeds the threshold.
- **Protective Server-Side SL:** Injected into each individual MT5 order to protect against local network or machine failure.
