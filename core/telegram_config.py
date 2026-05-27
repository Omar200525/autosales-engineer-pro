"""Telegram notification settings loaded from environment variables."""

from __future__ import annotations

from dataclasses import dataclass
import os

from core import config as _loaded_config  # noqa: F401  Ensures .env is loaded once.


TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


class TelegramConfigError(RuntimeError):
    """Raised when Telegram notification settings are inconsistent."""


@dataclass(frozen=True)
class TelegramSettings:
    """Runtime settings for Telegram Bot API notifications."""

    enabled: bool
    bot_token: str
    chat_id: str
    include_pdf: bool
    bot_polling_enabled: bool
    polling_timeout_seconds: float
    timeout_seconds: float
    api_base_url: str

    def require_ready(self, *, require_chat_id: bool = True) -> None:
        """Validate settings required for sending a Telegram notification."""
        if not self.enabled:
            return
        missing = []
        if not self.bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if require_chat_id and not self.chat_id:
            missing.append("TELEGRAM_CHAT_ID")
        if missing:
            names = ", ".join(missing)
            raise TelegramConfigError(f"Telegram notifications are enabled but missing: {names}")
        if self.timeout_seconds <= 0:
            raise TelegramConfigError("TELEGRAM_TIMEOUT_SECONDS must be greater than 0")
        if self.polling_timeout_seconds <= 0:
            raise TelegramConfigError("TELEGRAM_POLLING_TIMEOUT_SECONDS must be greater than 0")
        if not self.api_base_url:
            raise TelegramConfigError("TELEGRAM_API_BASE_URL cannot be empty")


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    normalized = raw_value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise TelegramConfigError(f"{name} must be true or false")


def _env_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    try:
        return float(raw_value)
    except ValueError as exc:
        raise TelegramConfigError(f"{name} must be a number") from exc


def get_telegram_settings(*, validate: bool = True) -> TelegramSettings:
    """Return Telegram settings, optionally validating required send fields."""
    settings = TelegramSettings(
        enabled=_env_bool("TELEGRAM_ENABLED", False),
        bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        include_pdf=_env_bool("TELEGRAM_INCLUDE_PDF", True),
        bot_polling_enabled=_env_bool("TELEGRAM_BOT_POLLING_ENABLED", True),
        polling_timeout_seconds=_env_float("TELEGRAM_POLLING_TIMEOUT_SECONDS", 20.0),
        timeout_seconds=_env_float("TELEGRAM_TIMEOUT_SECONDS", 12.0),
        api_base_url=os.getenv("TELEGRAM_API_BASE_URL", "https://api.telegram.org").strip().rstrip("/"),
    )
    if validate:
        settings.require_ready()
    return settings


def telegram_notifications_requested() -> bool:
    """Return whether Telegram notifications are enabled by environment."""
    return get_telegram_settings(validate=False).enabled