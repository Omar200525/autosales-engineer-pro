"""Fallback helpers for resilient multi-provider execution."""

from __future__ import annotations

from typing import Any

from rich.console import Console

from core.config import GROQ_BASE_URL, GROQ_FALLBACK_MODEL, get_groq_client
from core.llm_utils import parse_json_response

console = Console()


def groq_json_completion(system_prompt: str, user_prompt: str, model: str | None = None) -> dict[str, Any]:
    """Run a JSON-only Groq completion and parse it."""
    groq_model = model or GROQ_FALLBACK_MODEL
    client = get_groq_client()
    response = client.chat.completions.create(
        model=groq_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
    )
    return parse_json_response(response.choices[0].message.content or "")


def groq_base_label() -> str:
    """Return the Groq fallback label used in API errors."""
    return f"{GROQ_BASE_URL} ({GROQ_FALLBACK_MODEL})"
