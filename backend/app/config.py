"""
MT5 Trading Terminal — Application Configuration
All secrets loaded from environment / .env file via pydantic-settings.
DEMO_ONLY=false is refused at startup (Section 2 / 0.2).
"""
from __future__ import annotations

import secrets
import sys
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── MT5 Connection ──────────────────────────────────────────────────────
    mt5_terminal_path: str = r"C:\Program Files\MetaTrader 5\terminal64.exe"
    mt5_login: int | None = None
    mt5_password: SecretStr | None = None
    mt5_server: str | None = None
    mt5_timeout_ms: int = 30_000

    # ── Safety gate ─────────────────────────────────────────────────────────
    demo_only: bool = True
    allowed_login: int | None = None  # if set, refuse any other login

    # ── Gold symbol ─────────────────────────────────────────────────────────
    gold_symbol: str = "XAUUSD"

    # ── Absolute hard ceilings (UI/config cannot exceed these) ──────────────
    absolute_max_lot: float = 1.0
    absolute_max_positions: int = 50
    absolute_max_total_lots: float = 5.0

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "sqlite:///./mt5terminal.db"

    # ── API Security ─────────────────────────────────────────────────────────
    api_token: SecretStr = Field(default_factory=lambda: SecretStr(secrets.token_hex(32)))

    # ── Server ───────────────────────────────────────────────────────────────
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    frontend_origin: str = "http://localhost:5173"

    # ── Logging ──────────────────────────────────────────────────────────────
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_file: str = "logs/mt5terminal.log"

    # ── Risk defaults ────────────────────────────────────────────────────────
    max_daily_loss_pct: float = 5.0
    max_drawdown_pct: float = 10.0
    max_spread_points: int = 100
    max_slippage_points: int = 30

    # ── Mode ─────────────────────────────────────────────────────────────────
    default_mode: Literal["DRY_RUN", "DEMO_EXECUTION"] = "DRY_RUN"
    server_tz_offset_hours: float | None = None

    # ── Validators ───────────────────────────────────────────────────────────
    @field_validator("demo_only", mode="before")
    @classmethod
    def enforce_demo_only(cls, v: object) -> bool:
        """V1 REFUSES to start if DEMO_ONLY is false. Section 2 [FIX]."""
        if isinstance(v, str):
            v = v.lower() not in ("false", "0", "no")
        if not v:
            print(
                "\n[FATAL] DEMO_ONLY=false is rejected in V1. "
                "This system does not support live-account trading. "
                "Set DEMO_ONLY=true and restart.\n",
                file=sys.stderr,
            )
            sys.exit(1)
        return bool(v)

    @model_validator(mode="after")
    def validate_ceilings(self) -> "Settings":
        if self.absolute_max_lot <= 0:
            raise ValueError("ABSOLUTE_MAX_LOT must be > 0")
        if self.absolute_max_positions <= 0:
            raise ValueError("ABSOLUTE_MAX_POSITIONS must be > 0")
        if self.absolute_max_total_lots <= 0:
            raise ValueError("ABSOLUTE_MAX_TOTAL_LOTS must be > 0")
        return self


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
