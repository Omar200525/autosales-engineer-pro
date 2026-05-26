"""Four-agent orchestration pipeline for AutoSales Engineer Pro."""

from __future__ import annotations

import itertools
import time
from typing import Callable, Optional

from agents.parser_agent import ParserAgent
from agents.reviewer_agent import ReviewerAgent
from agents.sales_engineer_agent import SalesEngineerAgent
from agents.visual_analyst_agent import VisualAnalystAgent
from core.catalog import get_product_by_id
from core.models import (
    AgentStep,
    CompatibilityMatrix,
    QuoteLineItem,
    ReviewerFeedback,
    SelfCritiqueResult,
    SolutionReport,
)
from core.tools import check_compatibility, check_delivery


def _pipeline_step(iteration: int, agent_name: str, action: str, summary: str) -> AgentStep:
    """Create a pipeline status step."""
    from core.llm_utils import now_iso

    return AgentStep.model_validate(
        {
            "iteration": iteration,
            "agent_name": agent_name,
            "action": action,
            "tool_called": None,
            "tool_args": None,
            "tool_result_summary": summary,
            "timestamp": now_iso(),
        }
    )


def _shipping_fee(location: str, regions: list[str]) -> float:
    """Estimate Malaysian shipping fee per line item."""
    location_lower = location.lower()
    if "nationwide" in regions or "kuala" in location_lower or location_lower == "kl":
        return 0.0
    if "sabah" in location_lower or "sarawak" in location_lower or "kinabalu" in location_lower or "kuching" in location_lower:
        return 45.0
    return 25.0


def _delivery_timeline(location: str) -> str:
    """Return a regional delivery timeline estimate."""
    lower = location.lower()
    if "sabah" in lower or "sarawak" in lower or "kinabalu" in lower or "kuching" in lower:
        return "East Malaysia: 5-10 business days"
    if "nationwide" in lower:
        return "Nationwide: 3-7 business days"
    return "West Malaysia: 2-5 business days"


class SalesEngineerPipeline:
    """Coordinates VisualAnalyst, Parser, SalesEngineer, and Reviewer agents."""

    def __init__(self) -> None:
        """Create agent instances."""
        self.visual_agent = VisualAnalystAgent()
        self.parser_agent = ParserAgent()
        self.sales_agent = SalesEngineerAgent()
        self.reviewer_agent = ReviewerAgent()

    def run(
        self,
        raw_brief: str,
        image_bytes: Optional[bytes] = None,
        image_media_type: Optional[str] = None,
        on_step: Optional[Callable[[AgentStep], None]] = None,
    ) -> SolutionReport:
        """Run the complete four-agent pipeline."""
        start = time.time()
        all_steps: list[AgentStep] = []

        def wrapped_step(step: AgentStep) -> None:
            all_steps.append(step)
            if on_step:
                on_step(step)

        visual_extraction = None
        if image_bytes is not None:
            if not image_media_type:
                raise ValueError("image_media_type is required when image_bytes is provided")
            wrapped_step(_pipeline_step(0, "VisualAnalyst", "Starting visual extraction", "Gemini 3.5 primary with Gemini 2.5 fallback"))
            visual_extraction = self.visual_agent.analyze(image_bytes, image_media_type, wrapped_step)

        wrapped_step(_pipeline_step(0, "Parser", "Starting requirements parser", "Groq parser with compact prompt and local fallback"))
        brief = self.parser_agent.parse(raw_brief, visual_extraction, wrapped_step)
        wrapped_step(_pipeline_step(0, "SalesEngineer", "Starting solution builder", "Chutes primary, Groq fallback, local catalog fallback"))
        solution = self.sales_agent.build_solution(brief, on_step=wrapped_step)
        wrapped_step(_pipeline_step(0, "Reviewer", "Starting senior reviewer", "Chutes primary, compact Groq fallback, local reviewer fallback"))
        reviewer_feedback = self.reviewer_agent.review(brief, solution, wrapped_step)

        if not reviewer_feedback.approved:
            wrapped_step(_pipeline_step(0, "SalesEngineer", "Reviewer requested revision", "Rebuilding solution with reviewer feedback"))
            solution = self.sales_agent.build_solution(brief, reviewer_feedback=reviewer_feedback, on_step=wrapped_step)
            wrapped_step(_pipeline_step(0, "Reviewer", "Reviewing revised solution", "Final QA pass after revision"))
            reviewer_feedback = self.reviewer_agent.review(brief, solution, wrapped_step)

        return self._assemble_report(
            brief=brief,
            solution=solution,
            reviewer_feedback=reviewer_feedback,
            all_steps=all_steps,
            duration=time.time() - start,
        )

    def _assemble_report(
        self,
        brief,
        solution: dict,
        reviewer_feedback: ReviewerFeedback,
        all_steps: list[AgentStep],
        duration: float,
    ) -> SolutionReport:
        selected = solution.get("selected_products", [])
        line_items: list[QuoteLineItem] = []
        selected_ids: list[str] = []
        warnings = list(solution.get("warnings", []))

        for item in selected:
            product = get_product_by_id(item.get("product_id", ""))
            if product is None:
                warnings.append(f"Selected product not found in catalog: {item.get('product_id')}")
                continue
            quantity = int(item.get("quantity", 1))
            subtotal = product.price_myr * quantity
            shipping = _shipping_fee(brief.delivery_location, product.available_regions)
            sst = 0.0 if product.category == "software_license" else subtotal * 0.08
            tco = subtotal + shipping + sst
            selected_ids.append(product.id)
            line_items.append(
                QuoteLineItem.model_validate(
                    {
                        "product_id": product.id,
                        "product_name": product.name,
                        "brand": product.brand,
                        "category": product.category,
                        "quantity": quantity,
                        "unit_price_myr": product.price_myr,
                        "subtotal_myr": subtotal,
                        "confidence_score": float(item.get("confidence_score", 0.75)),
                        "confidence_reason": item.get("confidence_reason", "Selected by Sales Engineer agent."),
                        "product_url": item.get("product_url") or product.url,
                        "source_platform": item.get("source_platform") or product.source_platform,
                        "shipping_fee_myr": shipping,
                        "sst_myr": sst,
                        "tco_myr": tco,
                    }
                )
            )

        pairs = []
        issues = []
        for a_id, b_id in itertools.combinations(selected_ids, 2):
            result = check_compatibility(a_id, b_id)
            data = result.data if result.success else {"compatible": False, "reason": result.error or "Unknown"}
            a_product = get_product_by_id(a_id)
            b_product = get_product_by_id(b_id)
            pair = {
                "a": a_id,
                "b": b_id,
                "a_name": a_product.name if a_product else a_id,
                "b_name": b_product.name if b_product else b_id,
                "compatible": bool(data["compatible"]),
                "reason": data["reason"],
            }
            pairs.append(pair)
            if not pair["compatible"]:
                issues.append(f"{a_id} and {b_id}: {pair['reason']}")

        delivery = check_delivery(selected_ids, brief.delivery_location)
        delivery_data = delivery.data if delivery.success else {"feasible": False, "unavailable_products": selected_ids}
        total = sum(item.subtotal_myr for item in line_items)
        tco_total = sum(item.tco_myr for item in line_items)
        utilization = (total / brief.budget_myr * 100) if brief.budget_myr else 0.0
        executive_summary = solution.get("solution_summary") or (
            f"Proposed IT solution for {brief.client_name} covering {', '.join(brief.inferred_categories)} "
            f"with a quoted subtotal of MYR {total:,.2f}."
        )
        critique_history = [
            SelfCritiqueResult.model_validate(item)
            for item in solution.get("self_critique_history", [])
        ]
        return SolutionReport.model_validate(
            {
                "client_name": brief.client_name,
                "use_case": brief.use_case,
                "delivery_location": brief.delivery_location,
                "line_items": [item.model_dump() for item in line_items],
                "total_price_myr": total,
                "budget_myr": brief.budget_myr,
                "within_budget": total <= brief.budget_myr,
                "budget_utilization_pct": utilization,
                "compatibility_matrix": {
                    "pairs_checked": pairs,
                    "all_compatible": not issues,
                    "issues": issues,
                },
                "delivery_feasible": bool(delivery_data.get("feasible", False)),
                "unavailable_products": delivery_data.get("unavailable_products", []),
                "self_critique_history": [item.model_dump() for item in critique_history],
                "reviewer_feedback": reviewer_feedback.model_dump(),
                "executive_summary": executive_summary,
                "recommendations": solution.get("recommendations", []),
                "warnings": warnings + reviewer_feedback.risk_flags,
                "agent_steps": [step.model_dump() for step in all_steps],
                "total_iterations": len(all_steps),
                "pipeline_duration_seconds": duration,
                "brief_source": brief.source,
                "reasoning_summary": solution.get("reasoning_summary", executive_summary),
                "delivery_timeline_estimate": _delivery_timeline(brief.delivery_location),
                "logistics_tco_total_myr": tco_total,
            }
        )
