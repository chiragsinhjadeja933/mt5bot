"""
MT5 Structured Exceptions — every MT5 failure becomes a typed exception.
Section 3 [ADD]: every MT5 call goes through a wrapper that raises structured exceptions.
"""
from __future__ import annotations


class Mt5Error(Exception):
    """Base class for all MT5-related errors."""
    def __init__(self, message: str, code: int = 0, retcode: int = 0) -> None:
        super().__init__(message)
        self.code = code          # mt5.last_error() code
        self.retcode = retcode    # order retcode if applicable

    def to_dict(self) -> dict:
        return {
            "error": type(self).__name__,
            "message": str(self),
            "code": self.code,
            "retcode": self.retcode,
        }


class Mt5NotInitialized(Mt5Error):
    """MT5 not initialized / terminal not running."""


class Mt5AuthFailed(Mt5Error):
    """Authorization failed (wrong credentials, wrong server, investor password)."""


class Mt5Disconnected(Mt5Error):
    """Lost connection to broker server."""


class Mt5OrderRejected(Mt5Error):
    """Broker rejected the order — retcode and reason included."""


class Mt5Timeout(Mt5Error):
    """MT5 call exceeded the timeout budget."""


class Mt5InvalidVolume(Mt5Error):
    """Volume violates broker constraints."""


class Mt5InvalidStops(Mt5Error):
    """SL/TP too close or invalid."""


class Mt5MarketClosed(Mt5Error):
    """Market is closed for this symbol."""


class Mt5AlgoTradingDisabled(Mt5Error):
    """Algorithmic trading is disabled in the terminal."""


class Mt5SymbolNotFound(Mt5Error):
    """Symbol could not be resolved or selected."""


class Mt5NotDemo(Mt5Error):
    """Account is not a DEMO account — operation refused."""


class Mt5AccountSwitched(Mt5Error):
    """Login or server changed mid-session — entries blocked."""


class Mt5AmbiguousOutcome(Mt5Error):
    """Order outcome is unknown (timeout/None return) — do NOT retry blindly."""


class Mt5DuplicateOrder(Mt5Error):
    """An order already exists for this basket level."""


class Mt5InsufficientMargin(Mt5Error):
    """Not enough free margin for the requested order."""
