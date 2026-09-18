"""
MT5 Gateway — THE ONLY place order_send/order_check are called. Section 3 [ADD].
TradingGateway abstract interface + Mt5Gateway implementation.
Demo re-verified before every order.
"""
from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import structlog

from app.mt5.errors import (
    Mt5OrderRejected, Mt5AmbiguousOutcome, Mt5Timeout,
    Mt5NotInitialized,
)
from app.mt5.retcodes import (
    get_retcode_info, is_transient_retcode, is_success_retcode,
    RETCODE_TABLE,
)
from app.mt5.symbols import SymbolSpec

log = structlog.get_logger(__name__)

# Magic number for connection tests (never confused with strategy)
TEST_MAGIC = 9999999


@dataclass
class OrderRequest:
    symbol: str
    order_type: int        # 0=BUY_MARKET, 1=SELL_MARKET
    volume: Decimal
    price: float           # BUY=ask, SELL=bid (current)
    sl: float = 0.0
    tp: float = 0.0
    deviation: int = 20    # max slippage in points
    magic: int = 0
    comment: str = ""
    filling_mode: int = 0  # determined from symbol_info
    correlation_id: str = ""

    def __post_init__(self) -> None:
        if not self.correlation_id:
            self.correlation_id = str(uuid.uuid4())


@dataclass
class OrderResult:
    request: OrderRequest
    retcode: int
    retcode_name: str
    order_ticket: int
    deal_ticket: int
    volume_filled: Decimal
    price_filled: float
    comment: str
    request_id: int
    success: bool
    latency_ms: float
    slippage_points: int   # requested vs filled
    raw_result: dict       # full MT5 result for audit

    def to_dict(self) -> dict:
        return {
            "correlation_id": self.request.correlation_id,
            "retcode": self.retcode,
            "retcode_name": self.retcode_name,
            "retcode_description": get_retcode_info(self.retcode).description,
            "human_fix": get_retcode_info(self.retcode).human_fix,
            "order_ticket": self.order_ticket,
            "deal_ticket": self.deal_ticket,
            "volume_filled": str(self.volume_filled),
            "price_filled": self.price_filled,
            "slippage_points": self.slippage_points,
            "comment": self.comment,
            "success": self.success,
            "latency_ms": round(self.latency_ms, 2),
        }


class TradingGateway(ABC):
    """
    Abstract gateway interface. Three implementations:
    - Mt5Gateway (real MT5)
    - DryRunGateway (virtual fills, real market data)
    - BacktestGateway (historical simulation)
    """

    @abstractmethod
    def get_account(self) -> Any:
        ...

    @abstractmethod
    def get_tick(self, symbol: str) -> Any:
        ...

    @abstractmethod
    def get_positions(self, symbol: str | None = None, magic: int | None = None) -> list:
        ...

    @abstractmethod
    def send_order(self, request: OrderRequest) -> OrderResult:
        ...

    @abstractmethod
    def close_position(self, ticket: int, symbol: str,
                       volume: Decimal, order_type: int,
                       price: float, deviation: int,
                       magic: int, comment: str) -> OrderResult:
        ...

    @abstractmethod
    def modify_position(self, ticket: int, sl: float, tp: float) -> bool:
        ...

    @abstractmethod
    def get_deals(self, position_id: int) -> list:
        ...

    @abstractmethod
    def order_calc_margin(self, order_type: int, symbol: str,
                          volume: Decimal, price: float) -> float | None:
        ...

    @abstractmethod
    def order_check(self, request: OrderRequest) -> tuple[int, str]:
        """Returns (retcode, comment). retcode 0 = OK."""
        ...


class Mt5Gateway(TradingGateway):
    """
    Real MT5 gateway — the ONLY place mt5.order_send() is called.
    All calls go through the MT5 worker thread via connection.
    Demo re-verified immediately before every order.
    """

    def __init__(self, connection: Any, spec_cache: dict[str, SymbolSpec] | None = None) -> None:
        self._conn = connection  # MT5Connection instance
        self._spec_cache: dict[str, SymbolSpec] = spec_cache or {}
        self._MAX_RETRY = 3

    def _worker(self, fn: Any) -> Any:
        return self._conn._run_in_worker(fn)

    def get_account(self) -> Any:
        from app.mt5.account import read_account
        return self._worker(lambda: read_account(self._conn.mt5))

    def get_tick(self, symbol: str) -> Any:
        from app.mt5.market_data import read_tick
        return self._worker(lambda: read_tick(symbol, self._conn.mt5))

    def get_positions(self, symbol: str | None = None, magic: int | None = None) -> list:
        from app.mt5.positions import read_positions
        return self._worker(lambda: read_positions(self._conn.mt5, symbol, magic))

    def get_deals(self, position_id: int) -> list:
        from app.mt5.history import get_deals_by_position
        return self._worker(lambda: get_deals_by_position(position_id, self._conn.mt5))

    def order_calc_margin(self, order_type: int, symbol: str,
                          volume: Decimal, price: float) -> float | None:
        def _do() -> float | None:
            mt5 = self._conn.mt5
            result = mt5.order_calc_margin(order_type, symbol, float(volume), price)
            return result
        return self._worker(_do)

    def order_check(self, request: OrderRequest) -> tuple[int, str]:
        def _do() -> tuple[int, str]:
            mt5 = self._conn.mt5
            req_dict = self._build_request_dict(request)
            result = mt5.order_check(req_dict)
            if result is None:
                code, msg = mt5.last_error()
                return code, msg
            return result.retcode, result.comment
        return self._worker(_do)

    def send_order(self, request: OrderRequest) -> OrderResult:
        """
        THE ONLY function that calls mt5.order_send().
        Re-verifies demo status immediately before every order.
        Retries only for transient, safe retcodes.
        """
        # 1. Re-verify demo status (cached ≤5s, invalidated on reconnect)
        self._conn.verify_demo_cached()

        start = time.monotonic()
        last_result: OrderResult | None = None

        for attempt in range(self._MAX_RETRY):
            try:
                result = self._worker(lambda: self._do_send(request))
                last_result = result

                if result.success:
                    return result

                info = get_retcode_info(result.retcode)
                if not is_transient_retcode(result.retcode):
                    log.warning("order_rejected_no_retry",
                                retcode=result.retcode,
                                name=info.name,
                                policy=info.policy,
                                correlation_id=request.correlation_id)
                    return result

                log.info("order_retry",
                         attempt=attempt + 1,
                         retcode=result.retcode,
                         correlation_id=request.correlation_id)
                time.sleep(0.3 * (attempt + 1))  # backoff

            except Mt5Timeout as e:
                # AMBIGUOUS OUTCOME — do NOT retry blindly
                latency = (time.monotonic() - start) * 1000
                log.error("order_timeout_ambiguous",
                           error=str(e),
                           correlation_id=request.correlation_id)
                raise Mt5AmbiguousOutcome(
                    f"order_send timed out — outcome unknown. "
                    f"Query MT5 by magic={request.magic} before any retry. "
                    f"correlation_id={request.correlation_id}"
                ) from e

        return last_result  # type: ignore[return-value]

    def _do_send(self, request: OrderRequest) -> OrderResult:
        mt5 = self._conn.mt5
        if mt5 is None:
            raise Mt5NotInitialized("MT5 not initialized")

        req_dict = self._build_request_dict(request)
        log.info("order_send_request", **{k: str(v) for k, v in req_dict.items()
                                           if k not in ("password",)})

        t0 = time.monotonic()
        result = mt5.order_send(req_dict)
        latency_ms = (time.monotonic() - t0) * 1000

        if result is None:
            code, msg = mt5.last_error()
            # None result = possibly ambiguous — caller must decide retry policy
            raise Mt5AmbiguousOutcome(
                f"order_send returned None: [{code}] {msg}. "
                "Do NOT retry blindly — check positions/orders first.",
                code=code,
            )

        info = get_retcode_info(result.retcode)
        success = is_success_retcode(result.retcode)

        # Compute slippage
        filled_price = result.price if hasattr(result, "price") else 0.0
        sym_info = mt5.symbol_info(request.symbol)
        point = sym_info.point if sym_info else 0.01
        slippage = round(abs(filled_price - request.price) / point) if filled_price else 0

        log.info("order_send_result",
                 retcode=result.retcode,
                 retcode_name=info.name,
                 success=success,
                 latency_ms=round(latency_ms, 2),
                 slippage_points=slippage,
                 correlation_id=request.correlation_id)

        return OrderResult(
            request=request,
            retcode=result.retcode,
            retcode_name=info.name,
            order_ticket=result.order if hasattr(result, "order") else 0,
            deal_ticket=result.deal if hasattr(result, "deal") else 0,
            volume_filled=Decimal(str(result.volume)) if hasattr(result, "volume") else Decimal("0"),
            price_filled=filled_price,
            comment=result.comment if hasattr(result, "comment") else "",
            request_id=result.request_id if hasattr(result, "request_id") else 0,
            success=success,
            latency_ms=latency_ms,
            slippage_points=slippage,
            raw_result={
                "retcode": result.retcode,
                "deal": getattr(result, "deal", 0),
                "order": getattr(result, "order", 0),
                "volume": str(getattr(result, "volume", 0)),
                "price": getattr(result, "price", 0),
                "bid": getattr(result, "bid", 0),
                "ask": getattr(result, "ask", 0),
                "comment": getattr(result, "comment", ""),
            },
        )

    def close_position(self, ticket: int, symbol: str, volume: Decimal,
                       order_type: int, price: float, deviation: int,
                       magic: int, comment: str) -> OrderResult:
        """Close a position. order_type should be opposite direction."""
        close_req = OrderRequest(
            symbol=symbol,
            order_type=order_type,
            volume=volume,
            price=price,
            deviation=deviation,
            magic=magic,
            comment=comment[:31],
        )

        def _do() -> OrderResult:
            mt5 = self._conn.mt5
            req_dict = self._build_request_dict(close_req)
            req_dict["position"] = ticket  # type: ignore
            req_dict["type_filling"] = self._get_filling(symbol, mt5)

            t0 = time.monotonic()
            result = mt5.order_send(req_dict)
            latency_ms = (time.monotonic() - t0) * 1000

            if result is None:
                code, msg = mt5.last_error()
                raise Mt5AmbiguousOutcome(f"close order_send returned None: [{code}] {msg}", code=code)

            info = get_retcode_info(result.retcode)
            # 10036 = already closed = success
            success = is_success_retcode(result.retcode) or result.retcode == 10036

            return OrderResult(
                request=close_req,
                retcode=result.retcode,
                retcode_name=info.name,
                order_ticket=getattr(result, "order", 0),
                deal_ticket=getattr(result, "deal", 0),
                volume_filled=Decimal(str(getattr(result, "volume", 0))),
                price_filled=getattr(result, "price", 0.0),
                comment=getattr(result, "comment", ""),
                request_id=getattr(result, "request_id", 0),
                success=success,
                latency_ms=latency_ms,
                slippage_points=0,
                raw_result={"retcode": result.retcode},
            )

        return self._worker(_do)

    def modify_position(self, ticket: int, sl: float, tp: float) -> bool:
        def _do() -> bool:
            mt5 = self._conn.mt5
            req = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "sl": sl,
                "tp": tp,
            }
            result = mt5.order_send(req)
            if result is None:
                return False
            return result.retcode in {10009, 10025}  # DONE or NO_CHANGES
        return self._worker(_do)

    def _build_request_dict(self, req: OrderRequest) -> dict:
        mt5 = self._conn.mt5
        filling = self._get_filling(req.symbol, mt5)

        # BUY=0=ORDER_TYPE_BUY, SELL=1=ORDER_TYPE_SELL
        action = mt5.TRADE_ACTION_DEAL

        return {
            "action": action,
            "symbol": req.symbol,
            "volume": float(req.volume),
            "type": req.order_type,
            "price": req.price,
            "sl": req.sl,
            "tp": req.tp,
            "deviation": req.deviation,
            "magic": req.magic,
            "comment": req.comment[:31],  # MT5 comment max 31 chars
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }

    def _get_filling(self, symbol: str, mt5: Any) -> int:
        """Detect correct filling mode from symbol_info.filling_mode."""
        info = mt5.symbol_info(symbol)
        if info is None:
            return 0  # FOK default
        if info.filling_mode & 1:
            return mt5.ORDER_FILLING_FOK
        if info.filling_mode & 2:
            return mt5.ORDER_FILLING_IOC
        if info.filling_mode & 4:
            return mt5.ORDER_FILLING_RETURN
        return mt5.ORDER_FILLING_FOK
