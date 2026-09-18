"""
MT5 Retcode & Error Table — Section 49
Maps retcodes → (name, description, policy).
Verify each value against official MT5 documentation.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum
from typing import Literal


RetryPolicy = Literal["retry", "no_retry", "bounded_retry", "backoff", "noop", "fix_config"]


@dataclass(frozen=True)
class RetcodeInfo:
    code: int
    name: str
    description: str
    policy: RetryPolicy
    human_fix: str = ""


# ── MT5 Trade Server Retcodes ────────────────────────────────────────────────
RETCODE_TABLE: dict[int, RetcodeInfo] = {
    10004: RetcodeInfo(10004, "REQUOTE", "Price requoted", "bounded_retry",
                       "Retry with fresh price within deviation policy."),
    10006: RetcodeInfo(10006, "REJECT", "Request rejected by dealer", "no_retry",
                       "Log and alert; check with broker if persistent."),
    10007: RetcodeInfo(10007, "CANCEL", "Request canceled by trader", "noop",
                       "No action required."),
    10008: RetcodeInfo(10008, "PLACED", "Pending order placed", "noop",
                       "Verify order exists in MT5."),
    10009: RetcodeInfo(10009, "DONE", "Request completed", "noop",
                       "Verify via positions/deals."),
    10010: RetcodeInfo(10010, "DONE_PARTIAL", "Request partially executed", "noop",
                       "Track actual volume; apply policy for remainder."),
    10013: RetcodeInfo(10013, "INVALID", "Invalid request", "fix_config",
                       "Bug or config problem — block entries and alert."),
    10014: RetcodeInfo(10014, "INVALID_VOLUME", "Invalid volume", "fix_config",
                       "Do not auto-retry — fix sizing logic."),
    10015: RetcodeInfo(10015, "INVALID_PRICE", "Invalid price", "bounded_retry",
                       "Refresh price and retry within bounds."),
    10016: RetcodeInfo(10016, "INVALID_STOPS", "Invalid stops (SL/TP too close)", "no_retry",
                       "Recompute SL/TP against stops_level. Do not blind-retry."),
    10017: RetcodeInfo(10017, "TRADE_DISABLED", "Trading disabled", "no_retry",
                       "Block entries and alert operator."),
    10018: RetcodeInfo(10018, "MARKET_CLOSED", "Market closed", "no_retry",
                       "Block entries; do not raise alert storm."),
    10019: RetcodeInfo(10019, "NO_MONEY", "Insufficient funds", "no_retry",
                       "Block entries; raise risk event."),
    10020: RetcodeInfo(10020, "PRICE_CHANGED", "Prices changed", "bounded_retry",
                       "Retry with fresh price within bounds."),
    10021: RetcodeInfo(10021, "PRICE_OFF", "No quotes available", "backoff",
                       "Block entries; retry later."),
    10024: RetcodeInfo(10024, "TOO_MANY_REQUESTS", "Too many requests (rate limited)", "backoff",
                       "Back off and throttle MT5 call rate."),
    10025: RetcodeInfo(10025, "NO_CHANGES", "Nothing to modify", "noop",
                       "Treat as success — no change needed."),
    10027: RetcodeInfo(10027, "CLIENT_DISABLES_AT", "Algo trading disabled in terminal", "fix_config",
                       "Click 'Algo Trading' button in MT5 toolbar and retry."),
    10028: RetcodeInfo(10028, "LOCKED", "Order locked for processing", "backoff",
                       "Wait and retry later."),
    10029: RetcodeInfo(10029, "FROZEN", "Order/position frozen", "backoff",
                       "Wait; alert operator."),
    10030: RetcodeInfo(10030, "INVALID_FILL", "Unsupported filling mode", "bounded_retry",
                       "Re-detect filling mode from symbol_info and retry."),
    10031: RetcodeInfo(10031, "CONNECTION", "No connection to trade server", "retry",
                       "Trigger reconnect flow."),
    10032: RetcodeInfo(10032, "ONLY_REAL", "Only live accounts allowed", "fix_config",
                       "This is a configuration error — live trading not supported in V1."),
    10033: RetcodeInfo(10033, "LIMIT_ORDERS", "Broker order limit hit", "no_retry",
                       "Block entries; alert operator."),
    10034: RetcodeInfo(10034, "LIMIT_VOLUME", "Broker volume limit hit", "no_retry",
                       "Block entries; alert operator."),
    10036: RetcodeInfo(10036, "POSITION_CLOSED", "Position already closed", "noop",
                       "Treat as success-if-verified for close operations."),
}

# ── Python mt5.last_error() codes ────────────────────────────────────────────
LAST_ERROR_TABLE: dict[int, RetcodeInfo] = {
    1: RetcodeInfo(1, "OK", "No error", "noop"),
    -1: RetcodeInfo(-1, "FAIL", "Generic failure", "no_retry",
                    "Check terminal state and logs."),
    -2: RetcodeInfo(-2, "INVALID_PARAMS", "Invalid parameters", "fix_config",
                    "Check call arguments."),
    -4: RetcodeInfo(-4, "NOT_FOUND", "Not found", "no_retry",
                    "Symbol/position/order not found."),
    -6: RetcodeInfo(-6, "AUTH_FAILED", "Authorization failed", "no_retry",
                    "Check login, password, and server name. Investor password cannot trade."),
    -7: RetcodeInfo(-7, "UNSUPPORTED", "Unsupported", "no_retry",
                    "Feature not supported by broker."),
    -8: RetcodeInfo(-8, "AUTO_TRADING_DISABLED", "Auto trading disabled", "fix_config",
                    "Enable 'Algo Trading' in MT5 Options → Expert Advisors."),
    -10000: RetcodeInfo(-10000, "INTERNAL_FAIL", "Internal error", "retry"),
    -10001: RetcodeInfo(-10001, "INTERNAL_FAIL_SEND", "Internal send failed", "retry"),
    -10002: RetcodeInfo(-10002, "INTERNAL_FAIL_RECEIVE", "Internal receive failed", "retry"),
    -10003: RetcodeInfo(-10003, "INTERNAL_FAIL_INIT", "IPC initialize failed", "fix_config",
                        "Ensure MT5 terminal64.exe is running and not in a locked state."),
    -10004: RetcodeInfo(-10004, "INTERNAL_FAIL_CONNECT", "No connection to terminal", "retry",
                        "Start MetaTrader 5 terminal and try again."),
    -10005: RetcodeInfo(-10005, "INTERNAL_FAIL_TIMEOUT", "IPC timeout", "retry",
                        "Terminal may be busy; retry after a short wait."),
}


def get_retcode_info(retcode: int) -> RetcodeInfo:
    return RETCODE_TABLE.get(
        retcode,
        RetcodeInfo(retcode, "UNKNOWN", f"Unknown retcode {retcode}", "no_retry",
                    "Consult MT5 documentation for this retcode."),
    )


def get_last_error_info(code: int) -> RetcodeInfo:
    return LAST_ERROR_TABLE.get(
        code,
        RetcodeInfo(code, "UNKNOWN", f"Unknown last_error code {code}", "no_retry"),
    )


def is_transient_retcode(retcode: int) -> bool:
    """True if it's safe to do a bounded retry with fresh price."""
    transient = {10004, 10015, 10020, 10021, 10024, 10028, 10029, 10030, 10031}
    return retcode in transient


def is_success_retcode(retcode: int) -> bool:
    return retcode in {10009, 10010, 10008}
