"""Agent 3: final solution review using Chutes DeepSeek-R1."""

from __future__ import annotations

from typing import Callable, Optional

from rich.console import Console

from core.config import CHUTES_BASE_URL, GROQ_FALLBACK_MODEL, REVIEWER_MODEL, get_chutes_client
from core.fallbacks import groq_json_completion
from core.llm_utils import friendly_api_error, now_iso, parse_json_response
from core.models import AgentStep, ReviewerFeedback, StructuredBrief

console = Console()

REVIEWER_SYSTEM_PROMPT = """You are a Senior IT Consultant and Solution Architect with deep expertise
in enterprise IT infrastructure procurement in Southeast Asia, specifically
Malaysia.

You are conducting a final QA review of a proposed IT solution.

Evaluate:
1. Technical soundness - do components actually work together?
2. Commercial value - is this good value for money in the Malaysian market?
3. Risk flags - single points of failure, missing redundancy, gaps?
4. Scalability - can this grow with the business?
5. Vendor diversity - too dependent on one vendor?

Give:
- technical_score: 0-10 (engineering quality)
- commercial_score: 0-10 (value for money)
- approved: true only if both scores >= 6.5

Be thorough but fair. Consider budget constraints.

Respond ONLY with valid JSON - no preamble, no markdown fences:
{
  "approved": bool,
  "risk_flags": [list of strings],
  "suggestions": [list of strings],
  "overall_assessment": "2-3 sentence assessment",
  "technical_score": float,
  "commercial_score": float
}"""


class ReviewerAgent:
    """Performs the senior QA review."""

    def review(
        self,
        brief: StructuredBrief,
        solution: dict,
        on_step: Optional[Callable[[AgentStep], None]] = None,
    ) -> ReviewerFeedback:
        """Review a proposed solution."""
        client = get_chutes_client()
        messages = [
            {"role": "system", "content": REVIEWER_SYSTEM_PROMPT},
            {"role": "user", "content": f"Brief:\n{brief.model_dump_json()}\n\nSolution:\n{solution}"},
        ]
        try:
            response = client.chat.completions.create(model=REVIEWER_MODEL, messages=messages, timeout=60)
            content = response.choices[0].message.content or ""
            try:
                data = parse_json_response(content)
            except Exception:
                retry = messages + [{"role": "user", "content": "Respond ONLY with valid JSON."}]
                response = client.chat.completions.create(model=REVIEWER_MODEL, messages=retry, timeout=60)
                data = parse_json_response(response.choices[0].message.content or "")
            feedback = ReviewerFeedback.model_validate(data)
        except Exception as exc:
            console.log(f"[yellow]Reviewer primary failed; using Groq fallback: {exc}[/yellow]")
            try:
                compact_solution = {
                    "selected_products": solution.get("selected_products", [])[:12],
                    "total_estimated_myr": solution.get("total_estimated_myr"),
                    "solution_summary": solution.get("solution_summary", ""),
                    "warnings": solution.get("warnings", []),
                }
                data = groq_json_completion(
                    REVIEWER_SYSTEM_PROMPT,
                    f"Brief:\n{brief.model_dump_json()}\n\nCompact solution:\n{compact_solution}",
                    model=GROQ_FALLBACK_MODEL,
                )
                feedback = ReviewerFeedback.model_validate(data)
            except Exception as fallback_exc:
                console.log(f"[yellow]Reviewer fallback failed; using local reviewer: {fallback_exc}[/yellow]")
                feedback = self._local_review(brief, solution, str(fallback_exc))
        if on_step:
            on_step(
                AgentStep.model_validate(
                    {
                        "iteration": 1,
                        "agent_name": "Reviewer",
                        "action": "Reviewed final solution quality and risk",
                        "tool_called": None,
                        "tool_args": None,
                        "tool_result_summary": f"Approved={feedback.approved}; technical={feedback.technical_score:.1f}; commercial={feedback.commercial_score:.1f}",
                        "timestamp": now_iso(),
                    }
                )
            )
        return feedback

    def _local_review(self, brief: StructuredBrief, solution: dict, provider_error: str) -> ReviewerFeedback:
        """Return a deterministic reviewer assessment when providers fail."""
        selected = solution.get("selected_products", [])
        covered = len(selected)
        warnings = list(solution.get("warnings", []))
        if provider_error:
            warnings.append("Cloud reviewer unavailable; local reviewer fallback used.")
        total = float(solution.get("total_estimated_myr") or 0.0)
        commercial_score = 7.0 if total <= brief.budget_myr else 5.8
        technical_score = 7.0 if covered >= max(1, len(brief.inferred_categories)) else 6.0
        approved = technical_score >= 6.5 and commercial_score >= 6.5
        return ReviewerFeedback.model_validate(
            {
                "approved": approved,
                "risk_flags": warnings,
                "suggestions": [
                    "Confirm exact stock and warranty terms with supplier before purchase.",
                    "Have an engineer validate final installation quantities onsite.",
                ],
                "overall_assessment": (
                    "Local reviewer fallback completed the QA pass because cloud review was unavailable. "
                    "The proposal is suitable as a budgetary quote if product availability and installation scope are confirmed."
                ),
                "technical_score": technical_score,
                "commercial_score": commercial_score,
            }
        )
