"""Fallback helpers for resilient multi-provider execution."""

from __future__ import annotations

from typing import Any

from rich.console import Console

from core.config import GROQ_BASE_URL, GROQ_FALLBACK_MODEL, get_groq_client
from core.llm_utils import parse_json_response

console = Console()


def _truncate_text(text: str, max_chars: int) -> str:
    """Trim text while preserving a hint that content was compacted."""
    clean = " ".join((text or "").split())
    if len(clean) <= max_chars:
        return clean
    return clean[: max_chars - 29].rstrip() + "\n\n[content truncated for size]"


def _compact_prompts(system_prompt: str, user_prompt: str, *, system_max: int, user_max: int, total_max: int) -> tuple[str, str]:
    """Compact prompts to reduce TPM pressure for Groq free/on-demand tiers."""
    system = _truncate_text(system_prompt, system_max)
    user = _truncate_text(user_prompt, user_max)
    total = len(system) + len(user)
    if total <= total_max:
        return system, user
    overflow = total - total_max
    # Trim user first (usually the largest payload), then system if needed.
    user_budget = max(300, len(user) - overflow)
    user = _truncate_text(user, user_budget)
    total = len(system) + len(user)
    if total > total_max:
        system_budget = max(300, len(system) - (total - total_max))
        system = _truncate_text(system, system_budget)
    return system, user


def _is_groq_token_limit_error(exc: Exception) -> bool:
    """Detect Groq request size / token-per-minute limit failures."""
    text = str(exc).lower()
    patterns = [
        "request too large",
        "tokens per minute",
        "tpm",
        "rate_limit_exceeded",
        "limit",
    ]
    return any(pattern in text for pattern in patterns)


def groq_json_completion(system_prompt: str, user_prompt: str, model: str | None = None) -> dict[str, Any]:
    """Run a JSON-only Groq completion and parse it."""
    groq_model = model or GROQ_FALLBACK_MODEL
    client = get_groq_client()
    compact_system, compact_user = _compact_prompts(
        system_prompt,
        user_prompt,
        system_max=1800,
        user_max=3200,
        total_max=4600,
    )
    try:
        response = client.chat.completions.create(
            model=groq_model,
            messages=[
                {"role": "system", "content": compact_system},
                {"role": "user", "content": compact_user},
            ],
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        if not _is_groq_token_limit_error(exc):
            raise
        console.log("[yellow]Groq payload too large; retrying with tighter prompt compaction.[/yellow]")
        retry_system, retry_user = _compact_prompts(
            system_prompt,
            user_prompt,
            system_max=900,
            user_max=1700,
            total_max=2400,
        )
        response = client.chat.completions.create(
            model=groq_model,
            messages=[
                {"role": "system", "content": retry_system},
                {"role": "user", "content": retry_user},
            ],
            response_format={"type": "json_object"},
        )
    return parse_json_response(response.choices[0].message.content or "")


def groq_base_label() -> str:
    """Return the Groq fallback label used in API errors."""
    return f"{GROQ_BASE_URL} ({GROQ_FALLBACK_MODEL})"
