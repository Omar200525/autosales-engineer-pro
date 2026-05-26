"""Agent 0: vision-based brief extraction using Gemini."""

from __future__ import annotations

from typing import Callable, Optional

from rich.console import Console

from core.config import GROQ_FALLBACK_MODEL
from core.fallbacks import groq_json_completion
from core.gemini_client import attempted_vision_models, generate_vision_json
from core.llm_utils import friendly_api_error, now_iso, parse_json_response
from core.models import AgentStep, VisualExtraction

console = Console()

VISUAL_ANALYST_SYSTEM_PROMPT = """You are an expert at reading and extracting IT requirements from images.
The image may be a whiteboard, a scanned document, a hand-drawn diagram,
or a photo of an existing IT setup.

Your job: carefully examine the image and extract ALL relevant information.

Look for:
- Client or company name
- Budget figures (any currency - convert estimates to MYR if possible)
- Number of users or staff
- Location or delivery address
- Specific hardware or software requirements
- Network diagrams or topology hints
- Any text, annotations, or labels visible in the image

Respond ONLY with valid JSON - no preamble, no markdown fences:
{
  "raw_text_extracted": "everything readable in the image as plain text",
  "client_name": string or null,
  "detected_requirements": [list of requirement strings],
  "detected_budget_myr": float or null,
  "detected_location": string or null,
  "detected_num_users": int or null,
  "confidence": float between 0.0 and 1.0,
  "image_type": "whiteboard" | "document" | "diagram" | "photo" | "unknown"
}"""


class VisualAnalystAgent:
    """Extracts structured requirements from an uploaded image."""

    def analyze(
        self,
        image_bytes: bytes,
        image_media_type: str,
        on_step: Optional[Callable[[AgentStep], None]] = None,
    ) -> VisualExtraction:
        """Analyze an image and return a visual extraction."""
        if image_media_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValueError(f"Unsupported image type: {image_media_type}")
        try:
            content = generate_vision_json(image_bytes, image_media_type, VISUAL_ANALYST_SYSTEM_PROMPT)
            try:
                data = parse_json_response(content)
            except Exception:
                content = generate_vision_json(
                    image_bytes,
                    image_media_type,
                    f"{VISUAL_ANALYST_SYSTEM_PROMPT}\n\nRespond ONLY with valid JSON.",
                )
                data = parse_json_response(content)
            extraction = VisualExtraction.model_validate(data)
        except Exception as exc:
            console.log(f"[yellow]Gemini vision failed; using Groq metadata fallback: {exc}[/yellow]")
            try:
                data = groq_json_completion(
                    VISUAL_ANALYST_SYSTEM_PROMPT,
                    "The image could not be processed by Gemini. Return a conservative JSON object with "
                    "raw_text_extracted explaining that visual extraction was unavailable, no inferred client "
                    "details, confidence 0.0, image_type unknown, and one detected requirement asking the user "
                    "to provide text details if this was an image-only brief.",
                    model=GROQ_FALLBACK_MODEL,
                )
                extraction = VisualExtraction.model_validate(data)
            except Exception as fallback_exc:
                raise friendly_api_error(
                    "Gemini/Groq",
                    attempted_vision_models(),
                    f"Google AI Studio Gemini API; Groq fallback {GROQ_FALLBACK_MODEL}",
                    fallback_exc,
                ) from fallback_exc
        if on_step:
            on_step(
                AgentStep.model_validate(
                    {
                        "iteration": 1,
                        "agent_name": "VisualAnalyst",
                        "action": "Extracted requirements from uploaded image with Gemini vision fallback chain",
                        "tool_called": None,
                        "tool_args": None,
                        "tool_result_summary": (
                            f"{len(extraction.detected_requirements)} requirements, "
                            f"confidence {extraction.confidence:.2f}, type {extraction.image_type}"
                        ),
                        "timestamp": now_iso(),
                    }
                )
            )
        return extraction
