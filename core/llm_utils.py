"""Utilities for JSON-first LLM interactions."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any


def strip_json_fences(text: str) -> str:
    """Remove common markdown JSON fences from model output."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    return cleaned


def parse_json_response(text: str) -> dict[str, Any]:
    """Parse JSON after removing markdown fences."""
    return json.loads(strip_json_fences(text))


def now_iso() -> str:
    """Return the current local timestamp in ISO format."""
    return datetime.now().isoformat(timespec="seconds")


def message_to_dict(message: Any) -> dict:
    """Convert an OpenAI SDK message object to a serializable dict."""
    if hasattr(message, "model_dump"):
        return message.model_dump(exclude_none=True)
    if isinstance(message, dict):
        return {key: value for key, value in message.items() if value is not None}
    return dict(message)


def friendly_api_error(provider: str, model: str, base_url: str, exc: Exception) -> RuntimeError:
    """Return a concise provider-specific API error."""
    raw = str(exc)
    without_html = re.sub(r"<[^>]+>", " ", raw)
    clean = " ".join(without_html.split())
    if len(clean) > 420:
        clean = clean[:417] + "..."
    return RuntimeError(
        f"{provider} API call failed for model '{model}' at '{base_url}'. "
        f"Check the provider base URL, model access, and API key. Details: {clean}"
    )
