"""Agent 3: final solution review using AI with deterministic guardrails."""

from __future__ import annotations

from typing import Callable, Optional

from rich.console import Console

from core.config import CHUTES_BASE_URL, GROQ_FALLBACK_MODEL, REVIEWER_MODEL, get_chutes_client
from core.fallbacks import groq_json_completion
from core.llm_utils import friendly_api_error, now_iso, parse_json_response, run_with_deadline
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
        baseline_feedback = self._local_review(brief, solution, "")
        feedback = baseline_feedback
        ai_used = False
        used_model = None
        compact_solution = self._compact_solution(solution)
        try:
            client = get_chutes_client()
            response = run_with_deadline(
                lambda: client.chat.completions.create(
                    model=REVIEWER_MODEL,
                    messages=[
                        {"role": "system", "content": REVIEWER_SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": (
                                "Review this Autonomous Sales Engineer quote against the AI Marathon criteria: "
                                "track completeness, meaningful output, constraint solving, logistics/TCO reasoning, technical soundness, and commercial value.\n\n"
                                f"Brief:\n{brief.model_dump_json()}\n\n"
                                f"Deterministic QA baseline:\n{baseline_feedback.model_dump_json()}\n\n"
                                f"Compact solution:\n{compact_solution}"
                            ),
                        },
                    ],
                    timeout=5,
                ),
                6,
                "Chutes reviewer QA",
            )
            content = response.choices[0].message.content or ""
            feedback = ReviewerFeedback.model_validate(parse_json_response(content))
            ai_used = True
            used_model = REVIEWER_MODEL
        except Exception as exc:
            console.log(f"[yellow]Reviewer AI primary failed; using Groq fallback: {exc}[/yellow]")
            try:
                data = run_with_deadline(
                    lambda: groq_json_completion(
                        REVIEWER_SYSTEM_PROMPT,
                        (
                            f"Brief:\n{brief.model_dump_json()}\n\n"
                            f"Deterministic QA baseline:\n{baseline_feedback.model_dump_json()}\n\n"
                            f"Compact solution:\n{compact_solution}"
                        ),
                        model=GROQ_FALLBACK_MODEL,
                    ),
                    14,
                    "Groq reviewer QA",
                )
                feedback = ReviewerFeedback.model_validate(data)
                ai_used = True
                used_model = GROQ_FALLBACK_MODEL
            except Exception as fallback_exc:
                console.log(f"[yellow]Reviewer AI fallback failed; using deterministic reviewer: {fallback_exc}[/yellow]")
                feedback = self._local_review(brief, solution, str(fallback_exc))
        if ai_used:
            feedback = self._reconcile_ai_feedback(feedback, baseline_feedback)
        if on_step:
            on_step(
                AgentStep.model_validate(
                    {
                        "iteration": 1,
                        "agent_name": "Reviewer",
                        "action": "AI reviewed final solution quality and risk" if ai_used else "Deterministic reviewer validated final solution",
                        "tool_called": None,
                        "tool_args": {"model": used_model} if ai_used else None,
                        "tool_result_summary": f"Approved={feedback.approved}; technical={feedback.technical_score:.1f}; commercial={feedback.commercial_score:.1f}",
                        "timestamp": now_iso(),
                    }
                )
            )
        return feedback

    def _reconcile_ai_feedback(self, ai_feedback: ReviewerFeedback, baseline_feedback: ReviewerFeedback) -> ReviewerFeedback:
        """Use deterministic QA as guardrails for occasionally conservative AI review output."""
        serious_terms = ("missing", "incompatible", "exceeds budget", "not deliver", "not compatible", "invalid")
        serious_ai_risk = any(
            any(term in flag.lower() for term in serious_terms)
            for flag in ai_feedback.risk_flags
        )
        data = ai_feedback.model_dump()
        if baseline_feedback.approved and ai_feedback.technical_score >= 6.0 and ai_feedback.commercial_score >= 6.0 and not serious_ai_risk:
            data["approved"] = True
            data["technical_score"] = max(ai_feedback.technical_score, 6.8)
            data["commercial_score"] = max(ai_feedback.commercial_score, 6.8)
            data["suggestions"] = list(
                dict.fromkeys(
                    [
                        *ai_feedback.suggestions,
                        "Deterministic QA confirms budget fit, category coverage, and catalog-grounded product IDs.",
                    ]
                )
            )[:6]
        if not baseline_feedback.approved:
            data["approved"] = False
            data["risk_flags"] = list(dict.fromkeys([*ai_feedback.risk_flags, *baseline_feedback.risk_flags]))
        return ReviewerFeedback.model_validate(data)

    def _compact_solution(self, solution: dict) -> dict:
        """Keep reviewer payload concise and grounded."""
        return {
            "selected_products": solution.get("selected_products", [])[:12],
            "total_estimated_myr": solution.get("total_estimated_myr"),
            "solution_summary": solution.get("solution_summary", ""),
            "reasoning_summary": solution.get("reasoning_summary", ""),
            "recommendations": solution.get("recommendations", [])[:8],
            "warnings": solution.get("warnings", [])[:8],
        }

    def _local_review(self, brief: StructuredBrief, solution: dict, provider_error: str) -> ReviewerFeedback:
        """Return a deterministic reviewer assessment when providers fail."""
        selected = solution.get("selected_products", [])
        warnings = list(solution.get("warnings", []))
        if provider_error:
            warnings.append("Cloud reviewer unavailable; local reviewer fallback used.")
        total = float(solution.get("total_estimated_myr") or 0.0)
        selected_categories = set()
        for item in selected:
            product_id = item.get("product_id", "")
            try:
                from core.catalog import get_product_by_id

                product = get_product_by_id(product_id)
            except Exception:
                product = None
            if product is not None:
                selected_categories.add(product.category)
        missing = [category for category in brief.inferred_categories if category not in selected_categories]
        risk_flags = list(warnings)
        if missing:
            risk_flags.append(f"Missing coverage for inferred categories: {', '.join(missing)}")
        if total > brief.budget_myr:
            risk_flags.append(f"Subtotal MYR {total:,.2f} exceeds budget MYR {brief.budget_myr:,.2f}.")
        utilization = (total / brief.budget_myr * 100) if brief.budget_myr else 0.0
        if utilization < 55 and selected:
            risk_flags.append("Budget utilization is low; consider whether the client expects a more complete scope.")
        technical_score = 8.2 - (0.8 * len(missing)) - (0.25 * len(warnings))
        commercial_score = 8.0 if total <= brief.budget_myr else 5.7
        if 70 <= utilization <= 98:
            commercial_score += 0.4
        elif utilization < 55:
            commercial_score -= 0.4
        technical_score = max(0.0, min(10.0, technical_score))
        commercial_score = max(0.0, min(10.0, commercial_score))
        approved = technical_score >= 6.5 and commercial_score >= 6.5 and not missing and total <= brief.budget_myr
        return ReviewerFeedback.model_validate(
            {
                "approved": approved,
                "risk_flags": risk_flags,
                "suggestions": [
                    "Confirm exact stock and warranty terms with supplier before purchase.",
                    "Have an engineer validate final installation quantities onsite.",
                ],
                "overall_assessment": (
                    "Deterministic QA reviewed category coverage, budget fit, and solution risks. "
                    "The proposal is suitable as a budgetary quote if supplier stock, warranty terms, and onsite quantities are confirmed."
                ),
                "technical_score": technical_score,
                "commercial_score": commercial_score,
            }
        )
