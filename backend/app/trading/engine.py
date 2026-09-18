"""
Grid Trading Engine — Section 10, 11, 19.
Evaluates ticks against active grid configuration, manages basket P/L,
executes automated entry/scaling, and closes all basket positions at target TP ($3.00).
"""
from __future__ import annotations

import asyncio
import time
import uuid
from decimal import Decimal
from typing import Any

import structlog

from app.main import _system_state
from app.mt5.gateway import OrderRequest, TradingGateway
from app.trading.baskets import build_comment
from app.trading.dryrun import DryRunGateway
from app.trading.sizing import grid_lots_at_level
from app.trading.state_machine import BotState, ConnectionState, ExecutionMode

log = structlog.get_logger(__name__)


class GridTradingEngine:
    """
    Continuous trading engine loop.
    Polls market tick and open positions, enforces Basket TP/SL,
    and submits grid orders to the active gateway (MT5 demo or DryRun).
    """

    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task | None = None
        self._basket_id: str = str(uuid.uuid4())[:8]
        self._last_entry_price: Decimal | None = None
        self._last_entry_time: float = 0.0
        self._waiting_for_first_entry: bool = True
        self._closing_basket: bool = False
        self._rearm_until: float = 0.0

        # DryRun Gateway instance cache
        self._dry_gateway: DryRunGateway | None = None

    @property
    def basket_id(self) -> str:
        return self._basket_id

    def get_dry_gateway(self, real_gateway: TradingGateway) -> DryRunGateway:
        if self._dry_gateway is None:
            self._dry_gateway = DryRunGateway(real_gateway)
        return self._dry_gateway

    def reset_basket(self, reason: str = "tp_hit") -> None:
        """Reset basket state for next cycle (rearm)."""
        self._basket_id = str(uuid.uuid4())[:8]
        self._last_entry_price = None
        self._last_entry_time = 0.0
        self._waiting_for_first_entry = True
        self._closing_basket = False
        log.info("grid_engine_basket_reset", new_basket=self._basket_id, reason=reason)

    def get_active_gateway(self) -> TradingGateway | None:
        from app.api.mt5_routes import _gateway
        if _gateway is None:
            return None

        if _system_state.execution_mode == ExecutionMode.DEMO_EXECUTION:
            return _gateway
        else:
            return self.get_dry_gateway(_gateway)

    def get_basket_status(self) -> dict:
        """Return current active basket stats for UI and API."""
        gw = self.get_active_gateway()
        from app.api.strategy_routes import _current_strategy
        cfg = _current_strategy
        symbol = cfg.get("symbol", "XAUUSD")
        magic = cfg.get("magic", 10001)

        positions = gw.get_positions(symbol=symbol, magic=magic) if gw else []
        total_vol = sum(p.volume for p in positions) if positions else Decimal("0")
        total_profit = sum(
            Decimal(str(getattr(p, "profit", 0))) +
            Decimal(str(getattr(p, "swap", 0))) +
            Decimal(str(getattr(p, "entry_commission", 0)))
            for p in positions
        ) if positions else Decimal("0")

        avg_price = Decimal("0")
        if total_vol > 0 and positions:
            avg_price = sum(p.volume * Decimal(str(p.price_open)) for p in positions) / total_vol

        tp_target = Decimal(str(cfg.get("basket_take_profit", 3.0)))
        sl_target = Decimal(str(cfg.get("basket_stop_loss", 50.0)))

        progress_pct = 0.0
        if tp_target > 0:
            progress_pct = min(100.0, max(0.0, float(total_profit / tp_target * 100)))

        return {
            "basket_id": self._basket_id,
            "symbol": symbol,
            "direction": cfg.get("direction", "BUY"),
            "position_count": len(positions),
            "max_positions": cfg.get("max_positions", 40),
            "total_volume": str(total_vol),
            "weighted_avg_price": str(round(avg_price, 2)) if avg_price else None,
            "last_entry_price": str(self._last_entry_price) if self._last_entry_price else None,
            "floating_pnl": str(round(total_profit, 2)),
            "basket_tp": str(tp_target),
            "basket_sl": str(sl_target),
            "progress_pct": round(progress_pct, 1),
            "waiting_for_first_entry": self._waiting_for_first_entry,
            "closing_basket": self._closing_basket,
            "execution_mode": _system_state.execution_mode,
        }

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="grid_trading_engine")
        log.info("grid_trading_engine_started")

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("grid_trading_engine_stopped")

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._step()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("grid_engine_step_error", error=str(e))
            await asyncio.sleep(0.25)

    async def _step(self) -> None:
        # Check system readiness
        if _system_state.connection_state != ConnectionState.CONNECTED:
            return
        if _system_state.bot_state != BotState.RUNNING:
            return

        gw = self.get_active_gateway()
        if gw is None:
            return

        from app.api.strategy_routes import _current_strategy
        cfg = _current_strategy
        if not cfg.get("enabled", True):
            return

        symbol = cfg.get("symbol", "XAUUSD")
        magic = cfg.get("magic", 10001)

        # 1. Pull tick
        tick = gw.get_tick(symbol)
        if tick is None or getattr(tick, "is_stale", False):
            return

        bid = Decimal(str(tick.bid))
        ask = Decimal(str(tick.ask))
        spread_points = getattr(tick, "spread_points", 0)

        # 2. Pull open basket positions
        positions = gw.get_positions(symbol=symbol, magic=magic)

        # Compute basket floating P/L
        basket_pnl = sum(
            Decimal(str(getattr(p, "profit", 0))) +
            Decimal(str(getattr(p, "swap", 0))) +
            Decimal(str(getattr(p, "entry_commission", 0)))
            for p in positions
        ) if positions else Decimal("0")

        tp_target = Decimal(str(cfg.get("basket_take_profit", 3.0)))
        sl_target = Decimal(str(cfg.get("basket_stop_loss", 50.0)))
        rearm = cfg.get("rearm_after_basket_close", True)
        rearm_delay = float(cfg.get("rearm_delay_seconds", 5))

        # Check Rearm timer
        now_mono = time.monotonic()
        if self._rearm_until > 0:
            if now_mono < self._rearm_until:
                return
            else:
                self._rearm_until = 0.0

        # 3. Check Basket Take Profit
        if len(positions) > 0 and tp_target > 0 and basket_pnl >= tp_target:
            if not self._closing_basket:
                self._closing_basket = True
                log.info(
                    "basket_tp_triggered",
                    basket_id=self._basket_id,
                    pnl=str(basket_pnl),
                    target=str(tp_target),
                    positions=len(positions),
                )
                await self._close_basket_positions(gw, positions, symbol, magic, reason="basket_tp")
                if rearm:
                    self._rearm_until = now_mono + (rearm_delay if cfg.get("cooldown_seconds", 0) > 0 else 0.5)
                    self.reset_basket(reason="rearm_after_tp")
                return

        # 4. Check Basket Stop Loss
        if len(positions) > 0 and sl_target > 0 and basket_pnl <= -sl_target:
            if not self._closing_basket:
                self._closing_basket = True
                log.warning(
                    "basket_sl_triggered",
                    basket_id=self._basket_id,
                    pnl=str(basket_pnl),
                    target=str(sl_target),
                    positions=len(positions),
                )
                await self._close_basket_positions(gw, positions, symbol, magic, reason="basket_sl")
                self.reset_basket(reason="sl_hit")
                return

        # 5. Check if spread is too wide
        max_spread = cfg.get("max_spread_points", 60)
        if spread_points > max_spread:
            log.debug("grid_skip_spread_wide", spread=spread_points, max_spread=max_spread)
            return

        direction_str = cfg.get("direction", "BUY").upper()
        direction = 0 if direction_str == "BUY" else 1  # 0=BUY, 1=SELL
        initial_lot = Decimal(str(cfg.get("initial_lot", 0.01)))
        max_positions = int(cfg.get("max_positions", 40))
        grid_distance_points = int(cfg.get("grid_distance_points", 40))
        cooldown_s = float(cfg.get("cooldown_seconds", 0))

        # 6. Grid Entry Logic
        if len(positions) == 0:
            # Basket has 0 positions -> enter Level 0
            if self._waiting_for_first_entry or cfg.get("first_entry") == "immediate_on_start":
                price = ask if direction == 0 else bid
                comment = build_comment(
                    strategy_short=cfg.get("strategy_id", "xau")[:3],
                    direction="B" if direction == 0 else "S",
                    basket_short=self._basket_id[:6],
                    level=0,
                    nonce=str(uuid.uuid4())[:4],
                )
                await self._send_grid_order(
                    gw=gw,
                    symbol=symbol,
                    direction=direction,
                    volume=initial_lot,
                    price=price,
                    magic=magic,
                    comment=comment,
                    level=0,
                    cfg=cfg,
                )
        else:
            # Basket has positions -> evaluate grid expansion
            if len(positions) >= max_positions:
                return

            # Check cooldown
            if cooldown_s > 0:
                elapsed = now_mono - self._last_entry_time
                if elapsed < cooldown_s:
                    return

            # Determine anchor price
            grid_anchor = cfg.get("grid_anchor", "last_entry")
            if grid_anchor == "average_entry":
                total_v = sum(p.volume for p in positions)
                anchor_price = sum(p.volume * Decimal(str(p.price_open)) for p in positions) / total_v if total_v else Decimal(str(positions[-1].price_open))
            else:
                anchor_price = self._last_entry_price or Decimal(str(positions[-1].price_open))

            # Point distance (XAUUSD standard point is 0.01 = 1 pip / 10 cents)
            point = Decimal("0.01")
            grid_distance_price = Decimal(str(grid_distance_points)) * point

            # Check adverse trigger
            grid_mode = cfg.get("grid_mode", "adverse")
            triggered = False
            if direction == 0:  # BUY basket
                if grid_mode == "adverse":
                    # Buy adverse: price dropped by grid_distance
                    triggered = ask <= (anchor_price - grid_distance_price)
                else:
                    triggered = ask >= (anchor_price + grid_distance_price)
            else:  # SELL basket
                if grid_mode == "adverse":
                    # Sell adverse: price rose by grid_distance
                    triggered = bid >= (anchor_price + grid_distance_price)
                else:
                    triggered = bid <= (anchor_price - grid_distance_price)

            if triggered:
                level = len(positions)
                vol = grid_lots_at_level(
                    level=level,
                    initial_lot=initial_lot,
                    lot_mode=cfg.get("lot_mode", "fixed"),
                    lot_multiplier=float(cfg.get("lot_multiplier", 1.0)),
                    max_lot=Decimal(str(cfg.get("max_lot", 0.05))),
                )
                price = ask if direction == 0 else bid
                comment = build_comment(
                    strategy_short=cfg.get("strategy_id", "xau")[:3],
                    direction="B" if direction == 0 else "S",
                    basket_short=self._basket_id[:6],
                    level=level,
                    nonce=str(uuid.uuid4())[:4],
                )
                await self._send_grid_order(
                    gw=gw,
                    symbol=symbol,
                    direction=direction,
                    volume=vol,
                    price=price,
                    magic=magic,
                    comment=comment,
                    level=level,
                    cfg=cfg,
                )

    async def _send_grid_order(
        self,
        gw: TradingGateway,
        symbol: str,
        direction: int,
        volume: Decimal,
        price: Decimal,
        magic: int,
        comment: str,
        level: int,
        cfg: dict,
    ) -> bool:
        req = OrderRequest(
            symbol=symbol,
            order_type=direction,
            volume=volume,
            price=float(price),
            sl=0.0,
            tp=0.0,
            deviation=cfg.get("max_slippage_points", 30),
            magic=magic,
            comment=comment[:31],
        )

        try:
            res = gw.send_order(req)
            if res.success:
                fill_p = Decimal(str(res.price_filled or price))
                self._last_entry_price = fill_p
                self._last_entry_time = time.monotonic()
                self._waiting_for_first_entry = False
                log.info(
                    "grid_order_filled",
                    level=level,
                    direction="BUY" if direction == 0 else "SELL",
                    volume=str(volume),
                    fill_price=str(fill_p),
                    ticket=res.order_ticket,
                    basket_id=self._basket_id,
                )
                return True
            else:
                log.warning("grid_order_rejected", retcode=res.retcode, name=res.retcode_name)
                return False
        except Exception as e:
            log.error("grid_order_send_exception", error=str(e))
            return False

    async def _close_basket_positions(
        self,
        gw: TradingGateway,
        positions: list,
        symbol: str,
        magic: int,
        reason: str,
    ) -> None:
        log.info("closing_all_basket_positions", count=len(positions), reason=reason)
        for pos in positions:
            try:
                close_type = 1 if pos.type == 0 else 0
                tick = gw.get_tick(symbol)
                price = float(tick.bid) if close_type == 1 else float(tick.ask)
                gw.close_position(
                    ticket=pos.ticket,
                    symbol=pos.symbol,
                    volume=pos.volume,
                    order_type=close_type,
                    price=price,
                    deviation=50,
                    magic=magic,
                    comment=f"{reason[:12]}_{self._basket_id[:6]}",
                )
            except Exception as e:
                log.error("close_basket_position_failed", ticket=pos.ticket, error=str(e))


# Global singleton engine instance
_engine: GridTradingEngine | None = None


def get_trading_engine() -> GridTradingEngine:
    global _engine
    if _engine is None:
        _engine = GridTradingEngine()
    return _engine


def start_trading_engine() -> None:
    engine = get_trading_engine()
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(engine.start())
    except RuntimeError:
        pass
