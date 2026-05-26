"""Agent 1: requirements parser using Groq."""

from __future__ import annotations

import re
from typing import Callable, Optional

from rich.console import Console

from core.config import GROQ_BASE_URL, GROQ_FALLBACK_MODEL, GROQ_PARSER_MODEL, get_groq_client
from core.llm_utils import friendly_api_error, now_iso, parse_json_response
from core.models import AgentStep, StructuredBrief, VisualExtraction

console = Console()

PARSER_SYSTEM_PROMPT = """You are a requirements extraction specialist for IT procurement in Malaysia.
Your job: read a client's requirements (from text, image extraction, or both)
and produce a perfectly structured JSON object.

You must infer:
- inferred_categories: which product categories are needed
  (networking, compute, storage, display, peripheral, software_license,
   power, cooling) based on the use case
- priority: 'budget' if cost is emphasized, 'performance' if specs are
  emphasized, 'balanced' otherwise
- requirements: clean, actionable bullet points
- source: 'text' if only text, 'image' if only visual, 'combined' if both

All prices must be in MYR. If a budget is given in USD, multiply by 4.5.

Respond ONLY with valid JSON - no preamble, no markdown fences:
{
  "client_name": string,
  "use_case": string,
  "budget_myr": float,
  "delivery_location": string,
  "num_users": int or null,
  "requirements": [list of strings],
  "inferred_categories": [list of category strings],
  "priority": "budget" | "performance" | "balanced",
  "source": "text" | "image" | "combined"
}"""


class ParserAgent:
    """Normalizes raw text and visual extraction into a structured brief."""

    def parse(
        self,
        raw_brief: str,
        visual_extraction: Optional[VisualExtraction] = None,
        on_step: Optional[Callable[[AgentStep], None]] = None,
    ) -> StructuredBrief:
        """Parse a raw client brief."""
        client = get_groq_client()
        context = raw_brief
        if visual_extraction is not None:
            context = f"TEXT INPUT:\n{raw_brief}\n\nVISUAL EXTRACTION:\n{visual_extraction.model_dump_json()}"
        compact_prompt = self._compact_context(context)
        messages = [
            {"role": "system", "content": PARSER_SYSTEM_PROMPT},
            {"role": "user", "content": compact_prompt or "Use the visual extraction as the full brief."},
        ]
        try:
            try:
                response = client.chat.completions.create(model=GROQ_PARSER_MODEL, messages=messages, timeout=60)
                active_model = GROQ_PARSER_MODEL
            except Exception as primary_exc:
                console.log(f"[yellow]Groq parser primary failed; falling back: {primary_exc}[/yellow]")
                response = client.chat.completions.create(model=GROQ_FALLBACK_MODEL, messages=messages, timeout=60)
                active_model = GROQ_FALLBACK_MODEL
            content = response.choices[0].message.content or ""
            try:
                data = parse_json_response(content)
            except Exception:
                retry = messages + [{"role": "user", "content": "Respond ONLY with valid JSON."}]
                response = client.chat.completions.create(model=active_model, messages=retry, timeout=60)
                data = parse_json_response(response.choices[0].message.content or "")
            brief = StructuredBrief.model_validate(data)
        except Exception as exc:
            console.log(f"[yellow]Parser provider failed; using local parser fallback: {exc}[/yellow]")
            brief = self._local_parse(raw_brief, visual_extraction, str(exc))
        if on_step:
            on_step(
                AgentStep.model_validate(
                    {
                        "iteration": 1,
                        "agent_name": "Parser",
                        "action": "Parsed client brief into structured requirements",
                        "tool_called": None,
                        "tool_args": None,
                        "tool_result_summary": f"{brief.client_name}; {len(brief.inferred_categories)} categories; source={brief.source}",
                        "timestamp": now_iso(),
                    }
                )
            )
        return brief

    def _compact_context(self, context: str) -> str:
        """Keep Groq parser prompts below free-tier TPM limits."""
        if len(context) <= 2400:
            return context
        lines = [line.strip() for line in context.splitlines() if line.strip()]
        important = [
            line
            for line in lines
            if any(
                token in line.lower()
                for token in ["client", "use case", "budget", "location", "user", "requirement", "wifi", "nas", "ups", "server", "license"]
            )
        ]
        compact = "\n".join(important[:40])
        return compact[:2400] if compact else context[:2400]

    def _local_parse(
        self,
        raw_brief: str,
        visual_extraction: Optional[VisualExtraction],
        provider_error: str,
    ) -> StructuredBrief:
        """Parse a brief deterministically when Groq is rate-limited."""
        text = raw_brief or ""
        visual_requirements = []
        if visual_extraction is not None:
            visual_requirements = visual_extraction.detected_requirements
            text = f"{text}\n{visual_extraction.raw_text_extracted}\n" + "\n".join(visual_requirements)
        lower = text.lower()
        client_name = self._field(text, "Client") or (visual_extraction.client_name if visual_extraction else None) or "Client"
        use_case = self._field(text, "Use case") or self._first_sentence(text) or "IT procurement solution"
        location = self._field(text, "Delivery location") or (visual_extraction.detected_location if visual_extraction else None) or "Kuala Lumpur"
        budget_match = re.search(r"(?:myr|rm|budget[:\s]*)\s*([0-9][0-9,]*(?:\.\d+)?)", lower, re.IGNORECASE)
        budget = float(budget_match.group(1).replace(",", "")) if budget_match else (visual_extraction.detected_budget_myr if visual_extraction and visual_extraction.detected_budget_myr else 25000.0)
        users_match = re.search(r"(\d+)\s*(?:users|staff|seats|employees)", lower)
        users = int(users_match.group(1)) if users_match else (visual_extraction.detected_num_users if visual_extraction else None)
        requirements = self._requirements(text) + visual_requirements
        if not requirements:
            requirements = ["Provide a balanced IT solution matching the stated use case."]
        inferred = []
        keyword_map = {
            "networking": ["wifi", "network", "switch", "router", "firewall", "vpn", "internet"],
            "compute": ["server", "desktop", "pc", "workstation", "compute"],
            "storage": ["nas", "storage", "backup", "file sharing", "files"],
            "display": ["monitor", "display", "screen"],
            "peripheral": ["keyboard", "mouse", "webcam", "headset", "conference", "conferencing", "camera"],
            "software_license": ["microsoft 365", "license", "teams", "office", "software"],
            "power": ["ups", "power", "battery"],
            "cooling": ["rack", "cooling", "server room"],
        }
        for category, keywords in keyword_map.items():
            if any(keyword in lower for keyword in keywords):
                inferred.append(category)
        if not inferred:
            inferred = ["networking", "compute", "storage", "power"]
        priority = "budget" if "cheap" in lower or "budget" in lower else "performance" if "performance" in lower or "high" in lower else "balanced"
        source = "combined" if raw_brief and visual_extraction else "image" if visual_extraction else "text"
        if provider_error:
            requirements.append("Parser provider was rate-limited; deterministic parser fallback was used.")
        return StructuredBrief.model_validate(
            {
                "client_name": client_name,
                "use_case": use_case,
                "budget_myr": budget,
                "delivery_location": location,
                "num_users": users,
                "requirements": list(dict.fromkeys(requirements)),
                "inferred_categories": list(dict.fromkeys(inferred)),
                "priority": priority,
                "source": source,
            }
        )

    def _field(self, text: str, name: str) -> Optional[str]:
        """Extract a simple 'Field: value' line."""
        match = re.search(rf"^{re.escape(name)}:\s*(.+)$", text, re.IGNORECASE | re.MULTILINE)
        return match.group(1).strip() if match else None

    def _first_sentence(self, text: str) -> str:
        """Return a compact first useful sentence."""
        cleaned = " ".join(text.split())
        return cleaned[:220]

    def _requirements(self, text: str) -> list[str]:
        """Extract requirements after a requirements heading."""
        capture = False
        reqs = []
        for line in text.splitlines():
            clean = line.strip(" -\t")
            if not clean:
                continue
            if "requirements" in clean.lower():
                capture = True
                continue
            if capture:
                reqs.append(clean)
        return reqs[:20]
