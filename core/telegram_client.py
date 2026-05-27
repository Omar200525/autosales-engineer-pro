"""Small Telegram Bot API client used by backend notifications."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from core.telegram_config import TelegramSettings


MAX_TELEGRAM_TEXT_CHARS = 4096
MAX_TELEGRAM_CAPTION_CHARS = 1024


class TelegramDeliveryError(RuntimeError):
    """Raised when Telegram rejects or cannot receive a notification."""


@dataclass(frozen=True)
class TelegramDocument:
    """Document payload for Telegram sendDocument."""

    filename: str
    content: bytes
    caption: str = ""
    media_type: str = "application/pdf"


class TelegramClient:
    """Direct Telegram Bot API client using httpx."""

    def __init__(self, settings: TelegramSettings, transport: httpx.BaseTransport | None = None) -> None:
        settings.require_ready(require_chat_id=False)
        self._settings = settings
        self._transport = transport

    def send_message(self, text: str, chat_id: str | None = None) -> dict[str, Any]:
        """Send a plain-text Telegram message."""
        target_chat_id = self._target_chat_id(chat_id)
        message = text[:MAX_TELEGRAM_TEXT_CHARS] or "AutoSales Engineer Pro notification"
        return self._post(
            "sendMessage",
            data={
                "chat_id": target_chat_id,
                "text": message,
                "disable_web_page_preview": "true",
            },
        )

    def edit_message_text(self, chat_id: str, message_id: int, text: str) -> dict[str, Any]:
        """Edit an existing Telegram text message."""
        message = text[:MAX_TELEGRAM_TEXT_CHARS] or "AutoSales Engineer Pro notification"
        return self._post(
            "editMessageText",
            data={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": message,
                "disable_web_page_preview": "true",
            },
        )

    def send_document(self, document: TelegramDocument, chat_id: str | None = None) -> dict[str, Any]:
        """Send a document to Telegram."""
        target_chat_id = self._target_chat_id(chat_id)
        caption = document.caption[:MAX_TELEGRAM_CAPTION_CHARS]
        files = {"document": (document.filename, document.content, document.media_type)}
        data = {"chat_id": target_chat_id}
        if caption:
            data["caption"] = caption
        return self._post("sendDocument", data=data, files=files)

    def get_updates(
        self,
        *,
        offset: int | None = None,
        timeout_seconds: float | None = None,
        allowed_updates: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Long-poll Telegram updates."""
        data: dict[str, Any] = {}
        if offset is not None:
            data["offset"] = offset
        if timeout_seconds is not None:
            data["timeout"] = int(timeout_seconds)
        if allowed_updates is not None:
            import json

            data["allowed_updates"] = json.dumps(allowed_updates)
        response = self._post("getUpdates", data=data, request_timeout=(timeout_seconds or 0) + self._settings.timeout_seconds)
        result = response.get("result")
        return result if isinstance(result, list) else []

    def _post(
        self,
        method: str,
        *,
        data: dict[str, Any],
        files: dict[str, tuple[str, bytes, str]] | None = None,
        request_timeout: float | None = None,
    ) -> dict[str, Any]:
        url = f"{self._settings.api_base_url}/bot{self._settings.bot_token}/{method}"
        try:
            with httpx.Client(timeout=request_timeout or self._settings.timeout_seconds, transport=self._transport) as client:
                response = client.post(url, data=data, files=files)
        except httpx.RequestError as exc:
            raise TelegramDeliveryError(f"Telegram {method} request failed: {type(exc).__name__}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise TelegramDeliveryError(f"Telegram {method} returned a non-JSON response") from exc

        if response.status_code >= 400:
            description = _telegram_description(payload, f"HTTP {response.status_code}")
            raise TelegramDeliveryError(f"Telegram {method} failed: {description}")
        if not payload.get("ok"):
            description = _telegram_description(payload, "API response was not ok")
            raise TelegramDeliveryError(f"Telegram {method} failed: {description}")
        return payload

    def _target_chat_id(self, chat_id: str | None) -> str:
        target_chat_id = (chat_id or self._settings.chat_id).strip()
        if not target_chat_id:
            raise TelegramDeliveryError("Telegram chat ID is required")
        return target_chat_id


def _telegram_description(payload: Any, fallback: str) -> str:
    if isinstance(payload, dict):
        description = payload.get("description")
        if isinstance(description, str) and description.strip():
            return description.strip()
    return fallback