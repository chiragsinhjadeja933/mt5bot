"""
Connection Test Service — Section 5 [ADD]
Full 12-stage test sequence. Cleanup guarantee. Per-stage timing.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import structlog

log = structlog.get_logger(__name__)

TEST_MAGIC = 9_999_999


async def run_full_test(connection: Any, gateway: Any) -> dict:
    """
    Run the full MT5 connection test sequence per Section 5.
    Returns per-stage results and overall pass/fail.
    """
    stages: list[dict] = []
    opened_ticket: int | None = None

    def stage(name: str, passed: bool, detail: str = "",
              latency_ms: float = 0.0, retcode: int | None = None) -> dict:
        s = {
            "stage": name,
            "passed": passed,
            "detail": detail,
            "latency_ms": round(latency_ms, 2),
        }
        if retcode is not None:
            s["retcode"] = retcode
        stages.append(s)
        log.info("connection_test_stage", **s)
        return s

    try:
        # Stage 1: Demo confirmed
        t0 = time.monotonic()
        try:
            connection.verify_demo_cached()
            stage("DEMO_CONFIRMED", True, latency_ms=(time.monotonic() - t0) * 1000)
        except Exception as e:
            stage("DEMO_CONFIRMED", False, detail=str(e))
            return _result(stages, False, opened_ticket)

        # Stage 2: Read account
        t0 = time.monotonic()
        try:
            account = await asyncio.to_thread(gateway.get_account)
            stage("READ_ACCOUNT", True,
                  detail=f"login={account.login} balance={account.balance} {account.currency}",
                  latency_ms=(time.monotonic() - t0) * 1000)
        except Exception as e:
            stage("READ_ACCOUNT", False, detail=str(e))
            return _result(stages, False, opened_ticket)

        # Stage 3: Read XAUUSD
        t0 = time.monotonic()
        try:
            from app.config import get_settings
            symbol = get_settings().gold_symbol

            def _select_symbol():
                import MetaTrader5 as mt5
                mt5.symbol_select(symbol, True)
                info = mt5.symbol_info(symbol)
                return info

            sym_info = await asyncio.to_thread(
                lambda: connection._run_in_worker(_select_symbol)
            )
            if sym_info is None:
                raise ValueError(f"Symbol '{symbol}' not found")
            stage("READ_SYMBOL", True,
                  detail=f"{sym_info.name} digits={sym_info.digits} "
                         f"min={sym_info.volume_min} step={sym_info.volume_step}",
                  latency_ms=(time.monotonic() - t0) * 1000)
        except Exception as e:
            stage("READ_SYMBOL", False, detail=str(e))
            return _result(stages, False, opened_ticket)

        # Stage 4: Read bid/ask/spread
        t0 = time.monotonic()
        try:
            tick = await asyncio.to_thread(lambda: gateway.get_tick(symbol))
            stage("READ_TICK", True,
                  detail=f"bid={tick.bid} ask={tick.ask} spread={tick.spread_points}pts",
                  latency_ms=(time.monotonic() - t0) * 1000)
        except Exception as e:
            stage("READ_TICK", False, detail=str(e))
            return _result(stages, False, opened_ticket)

        # Stage 5: Pre-checks before placing order
        t0 = time.monotonic()
        try:
            from app.trading.sizing import BrokerVolumeSpec, validate_volume
            vol = Decimal("0.01")
            spec = BrokerVolumeSpec(
                volume_min=Decimal(str(sym_info.volume_min)),
                volume_max=Decimal(str(sym_info.volume_max)),
                volume_step=Decimal(str(sym_info.volume_step)),
                volume_limit=Decimal("0"),
            )
            err = validate_volume(vol, spec)
            if err:
                vol = Decimal(str(sym_info.volume_min))
            stage("PRE_CHECKS", True,
                  detail=f"volume={vol} OK",
                  latency_ms=(time.monotonic() - t0) * 1000)
        except Exception as e:
            stage("PRE_CHECKS", False, detail=str(e))
            return _result(stages, False, opened_ticket)

        # Stage 6: order_check (dry validation)
        t0 = time.monotonic()
        try:
            from app.mt5.gateway import OrderRequest
            req = OrderRequest(
                symbol=symbol,
                order_type=0,  # BUY
                volume=vol,
                price=float(tick.ask),
                deviation=30,
                magic=TEST_MAGIC,
                comment="mt5term-test",
            )
            retcode, comment = await asyncio.to_thread(lambda: gateway.order_check(req))
            passed = retcode == 0
            stage("ORDER_CHECK", passed,
                  detail=f"retcode={retcode} comment={comment}",
                  latency_ms=(time.monotonic() - t0) * 1000,
                  retcode=retcode)
            if not passed:
                return _result(stages, False, opened_ticket)
        except Exception as e:
            stage("ORDER_CHECK", False, detail=str(e))
            return _result(stages, False, opened_ticket)

        # Stage 7: Place 0.01 lot demo trade
        t0 = time.monotonic()
        try:
            result = await asyncio.to_thread(lambda: gateway.send_order(req))
            opened_ticket = result.order_ticket if result.success else None
            stage("PLACE_ORDER", result.success,
                  detail=f"ticket={result.order_ticket} retcode={result.retcode} "
                         f"filled={result.volume_filled}@{result.price_filled}",
                  latency_ms=(time.monotonic() - t0) * 1000,
                  retcode=result.retcode)
            if not result.success:
                return _result(stages, False, opened_ticket)
        except Exception as e:
            stage("PLACE_ORDER", False, detail=str(e))
            return _result(stages, False, opened_ticket)

        # Stage 8: Verify position exists
        t0 = time.monotonic()
        try:
            positions = await asyncio.to_thread(
                lambda: gateway.get_positions(symbol=symbol, magic=TEST_MAGIC)
            )
            pos = next((p for p in positions if p.ticket == opened_ticket), None)
            stage("VERIFY_POSITION", pos is not None,
                  detail=f"ticket={opened_ticket} profit={pos.profit if pos else '?'}",
                  latency_ms=(time.monotonic() - t0) * 1000)
        except Exception as e:
            stage("VERIFY_POSITION", False, detail=str(e))

        # Stage 9: Display floating P/L
        if pos:
            stage("FLOATING_PNL", True,
                  detail=f"profit={pos.profit} swap={pos.swap}")

        # Stage 10: Close position
        t0 = time.monotonic()
        close_success = False
        try:
            tick2 = await asyncio.to_thread(lambda: gateway.get_tick(symbol))
            close_result = await asyncio.to_thread(lambda: gateway.close_position(
                ticket=opened_ticket,
                symbol=symbol,
                volume=vol,
                order_type=1,  # SELL to close BUY
                price=float(tick2.bid),
                deviation=50,
                magic=TEST_MAGIC,
                comment="mt5term-test-close",
            ))
            close_success = close_result.success
            stage("CLOSE_POSITION", close_result.success,
                  detail=f"retcode={close_result.retcode}",
                  latency_ms=(time.monotonic() - t0) * 1000,
                  retcode=close_result.retcode)
        except Exception as e:
            stage("CLOSE_POSITION", False, detail=str(e))

        # Stage 11: Verify closed
        t0 = time.monotonic()
        try:
            positions2 = await asyncio.to_thread(
                lambda: gateway.get_positions(symbol=symbol, magic=TEST_MAGIC)
            )
            still_open = any(p.ticket == opened_ticket for p in positions2)
            stage("VERIFY_CLOSED", not still_open,
                  detail="Position confirmed closed" if not still_open else "Still open!",
                  latency_ms=(time.monotonic() - t0) * 1000)
        except Exception as e:
            stage("VERIFY_CLOSED", False, detail=str(e))

        # Stage 12: History
        t0 = time.monotonic()
        try:
            deals = await asyncio.to_thread(
                lambda: gateway.get_deals(opened_ticket)
            )
            stage("VERIFY_HISTORY", len(deals) >= 1,
                  detail=f"deals={len(deals)} profit={sum(d.net_profit for d in deals)}",
                  latency_ms=(time.monotonic() - t0) * 1000)
        except Exception as e:
            stage("VERIFY_HISTORY", False, detail=str(e))

        overall = all(s["passed"] for s in stages)
        return _result(stages, overall, opened_ticket, cleanup_succeeded=close_success)

    except Exception as e:
        stage("UNEXPECTED_ERROR", False, detail=str(e))
        # Cleanup guarantee — attempt to close test position
        if opened_ticket:
            try:
                tick_final = await asyncio.to_thread(lambda: gateway.get_tick(symbol))
                await asyncio.to_thread(lambda: gateway.close_position(
                    ticket=opened_ticket, symbol=symbol, volume=vol,
                    order_type=1, price=float(tick_final.bid),
                    deviation=100, magic=TEST_MAGIC, comment="test-cleanup",
                ))
                log.warning("connection_test_cleanup_success", ticket=opened_ticket)
            except Exception as ce:
                log.error("connection_test_cleanup_FAILED",
                          ticket=opened_ticket, error=str(ce))

        return _result(stages, False, opened_ticket)


def _result(stages: list, passed: bool, ticket: int | None,
            cleanup_succeeded: bool | None = None) -> dict:
    return {
        "overall_passed": passed,
        "stages": stages,
        "test_ticket": ticket,
        "cleanup_succeeded": cleanup_succeeded,
        "tested_at": datetime.now(timezone.utc).isoformat(),
    }
