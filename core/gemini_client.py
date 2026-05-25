"""Gemini helpers for the visual analyst agent."""

from __future__ import annotations

from google.genai import types

from core.config import GEMINI_FALLBACK_VISION_MODEL, GEMINI_VISION_MODEL, get_gemini_client


def generate_vision_json(image_bytes: bytes, image_media_type: str, prompt: str) -> str:
    """Generate JSON from an image and prompt with Gemini 3.5, then 2.5 fallback."""
    client = get_gemini_client()
    image_part = types.Part.from_bytes(data=image_bytes, mime_type=image_media_type)
    last_error: Exception | None = None
    for model in [GEMINI_VISION_MODEL, GEMINI_FALLBACK_VISION_MODEL]:
        try:
            response = client.models.generate_content(
                model=model,
                contents=[image_part, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            return response.text or ""
        except Exception as exc:
            last_error = exc
    raise RuntimeError(
        f"Gemini vision failed for both {GEMINI_VISION_MODEL} and "
        f"{GEMINI_FALLBACK_VISION_MODEL}: {last_error}"
    )


def attempted_vision_models() -> str:
    """Return a human-readable Gemini vision fallback chain."""
    return f"{GEMINI_VISION_MODEL} -> {GEMINI_FALLBACK_VISION_MODEL}"
