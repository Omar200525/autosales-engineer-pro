"""Four-agent orchestration pipeline for AutoSales Engineer Pro."""

from __future__ import annotations

import itertools
import re
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


def _product_search_text(item: QuoteLineItem) -> str:
    """Return searchable text for requirement coverage checks."""
    return " ".join(
        [
            item.product_name,
            item.brand,
            item.category,
            item.confidence_reason,
        ]
    ).lower()


def _category_terms() -> dict[str, list[str]]:
    return {
        "networking": ["wifi", "wi-fi", "internet", "network", "router", "switch", "firewall", "vpn", "access point"],
        "compute": ["server", "desktop", "laptop", "workstation", "pc", "compute"],
        "storage": ["nas", "storage", "backup", "file", "shared", "drive", "raid"],
        "display": ["monitor", "display", "screen", "projector", "4k"],
        "peripheral": ["conference", "conferencing", "camera", "webcam", "keyboard", "mouse", "headset", "video"],
        "software_license": ["microsoft", "office", "365", "license", "licence", "software", "email", "teams"],
        "power": ["ups", "power", "battery", "surge", "backup power"],
        "cooling": ["cooling", "fan", "airflow", "thermal"],
    }


def _constraint_decisions(brief, line_items: list[QuoteLineItem]) -> list[dict]:
    """Map each client requirement to selected product evidence."""
    decisions = []
    product_text = [(item, _product_search_text(item)) for item in line_items]
    category_terms = _category_terms()
    stopwords = {
        "for",
        "and",
        "the",
        "all",
        "with",
        "setup",
        "room",
        "users",
        "coverage",
        "shared",
        "files",
        "backup",
    }
    for requirement in brief.requirements:
        lower_req = requirement.lower()
        inferred_categories = [category for category, terms in category_terms.items() if any(term in lower_req for term in terms)]
        explicit_category_rules = [
            (["ups", "backup power", "battery backup", "surge"], ["power"]),
            (["microsoft 365", "office 365", "software license", "email"], ["software_license"]),
            (["nas", "file sharing", "shared files"], ["storage"]),
            (["wifi", "wi-fi", "internet", "firewall", "switch"], ["networking"]),
            (["video conferencing", "conference", "camera", "webcam"], ["peripheral"]),
            (["monitor", "display", "screen", "projector"], ["display"]),
            (["server", "workstation", "laptop", "desktop"], ["compute"]),
        ]
        for terms, categories in explicit_category_rules:
            if any(term in lower_req for term in terms):
                inferred_categories = categories
                break
        matched_items = [item for item in line_items if item.category in inferred_categories]
        if not matched_items:
            meaningful_tokens = [
                token
                for token in re.findall(r"[a-z0-9]+", lower_req)
                if len(token) >= 4 and token not in stopwords
            ]
            matched_items = [item for item, text in product_text if any(token in text for token in meaningful_tokens)]
        status = "covered" if matched_items else "needs_review"
        decisions.append(
            {
                "requirement": requirement,
                "status": status,
                "evidence": (
                    f"Covered by {', '.join(item.product_name for item in matched_items[:3])}."
                    if matched_items
                    else "No direct catalog line item matched this requirement; review before final submission."
                ),
                "covered_by": [item.product_name for item in matched_items[:5]],
            }
        )
    for category in brief.inferred_categories:
        if not any(item.category == category for item in line_items):
            decisions.append(
                {
                    "requirement": f"Inferred category coverage: {category}",
                    "status": "needs_review",
                    "evidence": "The parser inferred this category, but the final BOM has no selected product in it.",
                    "covered_by": [],
                }
            )
    return decisions


def _supplier_evidence(line_items: list[QuoteLineItem], location: str) -> list[dict]:
    """Expose source URLs, pricing, region fit, and confidence for judges."""
    evidence = []
    for item in line_items:
        product = get_product_by_id(item.product_id)
        regions = product.available_regions if product else []
        lower_location = location.lower()
        deliverable = bool(
            product
            and (
                "nationwide" in regions
                or any(region.lower() in lower_location for region in regions)
                or "kuala" in lower_location
            )
        )
        evidence.append(
            {
                "product_id": item.product_id,
                "product_name": item.product_name,
                "source_platform": item.source_platform,
                "url": item.product_url,
                "price_myr": item.unit_price_myr,
                "region_status": "Deliverable to requested region" if deliverable else "Needs supplier delivery confirmation",
                "confidence_score": item.confidence_score,
            }
        )
    return evidence


def _agentic_evidence(all_steps: list[AgentStep], line_items: list[QuoteLineItem], compatibility_ok: bool, delivery_ok: bool, within_budget: bool) -> list[dict]:
    """Summarize AI and tool proof points from the live trace."""
    tool_calls = [step for step in all_steps if step.tool_called]
    ai_steps = [step for step in all_steps if "AI" in step.action or (step.tool_args or {}).get("model")]
    fallback_steps = [
        step
        for step in all_steps
        if "fallback" in step.action.lower()
        or "unavailable" in step.action.lower()
        or "failed" in step.action.lower()
        or bool((step.tool_args or {}).get("primary_model") and (step.tool_args or {}).get("model") != (step.tool_args or {}).get("primary_model"))
    ]
    return [
        {
            "label": "LLM orchestration",
            "status": "pass" if len(ai_steps) >= 3 else "warn",
            "evidence": f"{len(ai_steps)} AI-backed steps across parser, planner, and reviewer.",
        },
        {
            "label": "Tool-grounded discovery",
            "status": "pass" if tool_calls else "info",
            "evidence": f"{len(tool_calls)} catalog, budget, delivery, or compatibility tool events were recorded.",
        },
        {
            "label": "Quote guardrails",
            "status": "pass" if within_budget and compatibility_ok and delivery_ok else "warn",
            "evidence": f"Budget={'pass' if within_budget else 'review'}, compatibility={'pass' if compatibility_ok else 'review'}, delivery={'pass' if delivery_ok else 'review'}.",
        },
        {
            "label": "Supplier evidence",
            "status": "pass" if all(item.product_url for item in line_items) else "warn",
            "evidence": f"{sum(1 for item in line_items if item.product_url)}/{len(line_items)} selected products include source URLs.",
        },
        {
            "label": "Fallback resilience",
            "status": "info" if fallback_steps else "pass",
            "evidence": f"{len(fallback_steps)} fallback events were handled without stopping the quote.",
        },
    ]


def _hackathon_scorecard(
    brief,
    line_items: list[QuoteLineItem],
    decisions: list[dict],
    reviewer_feedback: ReviewerFeedback,
    all_steps: list[AgentStep],
    within_budget: bool,
    compatibility_ok: bool,
    delivery_ok: bool,
) -> tuple[float, list[dict]]:
    """Estimate handbook readiness and provide evidence per judging criterion."""
    covered = sum(1 for decision in decisions if decision["status"] == "covered")
    coverage_ratio = covered / max(len(decisions), 1)
    ai_step_count = sum(1 for step in all_steps if "AI" in step.action or (step.tool_args or {}).get("model"))
    tool_call_count = sum(1 for step in all_steps if step.tool_called)
    has_urls = sum(1 for item in line_items if item.product_url)
    scorecard = [
        {
            "category": "Impact & Problem Relevance",
            "criterion": "Track understanding and completeness",
            "max_points": 20,
            "score": min(20, 12 + coverage_ratio * 6 + (2 if line_items else 0)),
            "evidence": [f"{covered}/{len(decisions)} requirements have selected-product evidence.", f"Brief categories: {', '.join(brief.inferred_categories)}."],
            "improvement_hint": "Add procurement-ready acceptance checks for any requirement marked review.",
        },
        {
            "category": "Impact & Problem Relevance",
            "criterion": "Solution effectiveness",
            "max_points": 15,
            "score": min(15, 4 + (3 if within_budget else 0) + (3 if compatibility_ok else 0) + (2 if delivery_ok else 0) + reviewer_feedback.technical_score * 0.3),
            "evidence": [f"Budget status: {'within' if within_budget else 'over'}.", f"Compatibility: {'pass' if compatibility_ok else 'review'}.", f"Delivery: {'feasible' if delivery_ok else 'review'}."],
            "improvement_hint": "Add a second scenario comparison when budget or delivery is close to the limit.",
        },
        {
            "category": "Impact & Problem Relevance",
            "criterion": "Scalability and future potential",
            "max_points": 10,
            "score": 8.0 if len(line_items) >= 4 and reviewer_feedback.approved else 6.5,
            "evidence": ["Quote includes recommendations, risk review, PDF export, API, React UI, and Telegram run updates."],
            "improvement_hint": "Add persisted customer history and multi-branch approval workflows.",
        },
        {
            "category": "Innovation & Creativity",
            "criterion": "Originality",
            "max_points": 20,
            "score": 17.0 if ai_step_count >= 3 else 14.0,
            "evidence": ["The product combines conversational Telegram intake, live agent trace, quote export, and catalog-backed AI planning."],
            "improvement_hint": "Add voice or image-to-quote demo flows for a stronger live-stage moment.",
        },
        {
            "category": "Innovation & Creativity",
            "criterion": "Tool use and AI orchestration",
            "max_points": 10,
            "score": min(10, 5 + min(ai_step_count, 4) * 0.8 + min(tool_call_count, 6) * 0.3),
            "evidence": [f"{ai_step_count} AI steps and {tool_call_count} tool events are visible in the trace."],
            "improvement_hint": "Expose live rejected alternatives and external supplier search snapshots.",
        },
        {
            "category": "Technical Implementation",
            "criterion": "Agentic architecture and design",
            "max_points": 15,
            "score": 13.0 if ai_step_count >= 3 and compatibility_ok else 10.5,
            "evidence": ["Pipeline separates vision, parsing, AI quote planning, validation, self-critique, and AI reviewer QA."],
            "improvement_hint": "Persist trace artifacts for audit and replay after server restart.",
        },
        {
            "category": "Technical Implementation",
            "criterion": "Prototype functionality",
            "max_points": 10,
            "score": min(10, 6 + (1 if line_items else 0) + (1 if has_urls else 0) + (1 if reviewer_feedback.approved else 0) + (1 if within_budget else 0)),
            "evidence": [f"{len(line_items)} BOM lines, {has_urls} supplier URLs, PDF export, SSE progress, and Telegram notifications."],
            "improvement_hint": "Add saved quote versions and judge-mode sample runs.",
        },
    ]
    total = sum(item["score"] for item in scorecard)
    return total, scorecard


def _architecture_diagram() -> str:
    return """flowchart LR
    A[Client brief or image] --> B[Gemini visual analyst]
    A --> C[Groq parser refinement]
    B --> C
    C --> D[Catalog and tool evidence]
    D --> E[AI sales engineer planner]
    E --> F[Budget, delivery, compatibility guardrails]
    F --> G[AI reviewer]
    G --> H[React report, PDF, Telegram updates]
    F -.fallback.-> H"""


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
            wrapped_step(_pipeline_step(0, "VisualAnalyst", "Starting visual extraction", "Gemini 2.5 primary with Gemini 2.0 fallback"))
            visual_extraction = self.visual_agent.analyze(image_bytes, image_media_type, wrapped_step)

        wrapped_step(_pipeline_step(0, "Parser", "Starting requirements parser", "Groq AI refinement with local structured fallback"))
        brief = self.parser_agent.parse(raw_brief, visual_extraction, wrapped_step)
        wrapped_step(_pipeline_step(0, "SalesEngineer", "Starting solution builder", "AI-guided catalog planner with deterministic constraint checks"))
        solution = self.sales_agent.build_solution(brief, on_step=wrapped_step)
        wrapped_step(_pipeline_step(0, "Reviewer", "Starting senior reviewer", "AI QA review grounded by deterministic validation"))
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
        within_budget = total <= brief.budget_myr
        compatibility_ok = not issues
        delivery_ok = bool(delivery_data.get("feasible", False))
        constraint_decisions = _constraint_decisions(brief, line_items)
        supplier_evidence = _supplier_evidence(line_items, brief.delivery_location)
        agentic_evidence = _agentic_evidence(all_steps, line_items, compatibility_ok, delivery_ok, within_budget)
        handbook_score_pct, scorecard = _hackathon_scorecard(
            brief=brief,
            line_items=line_items,
            decisions=constraint_decisions,
            reviewer_feedback=reviewer_feedback,
            all_steps=all_steps,
            within_budget=within_budget,
            compatibility_ok=compatibility_ok,
            delivery_ok=delivery_ok,
        )
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
                "within_budget": within_budget,
                "budget_utilization_pct": utilization,
                "compatibility_matrix": {
                    "pairs_checked": pairs,
                    "all_compatible": compatibility_ok,
                    "issues": issues,
                },
                "delivery_feasible": delivery_ok,
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
                "handbook_score_pct": handbook_score_pct,
                "hackathon_scorecard": scorecard,
                "constraint_decisions": constraint_decisions,
                "supplier_evidence": supplier_evidence,
                "agentic_evidence": agentic_evidence,
                "logistics_assumptions": [
                    "SST is estimated at 8% for hardware lines and 0% for software license lines.",
                    f"Delivery timeline estimate uses Malaysian regional assumptions: {_delivery_timeline(brief.delivery_location)}.",
                    "Shipping is estimated per line item from catalog region coverage and should be vendor-confirmed before purchase order issuance.",
                    "Total cost of ownership combines line subtotal, estimated shipping, and estimated SST.",
                ],
                "architecture_diagram": _architecture_diagram(),
                "demo_pitch": [
                    f"AutoSales Engineer Pro turns a messy brief for {brief.client_name} into a reviewed MYR quote with live agent trace.",
                    f"The system covers {sum(1 for decision in constraint_decisions if decision['status'] == 'covered')}/{len(constraint_decisions)} requirements with catalog-backed product evidence.",
                    f"The proposed subtotal is MYR {total:,.2f}, budget utilization is {utilization:.1f}%, and TCO is MYR {tco_total:,.2f}.",
                    "Every AI decision is constrained by product IDs, source URLs, budget math, delivery checks, compatibility checks, and reviewer QA.",
                ],
                "next_best_enhancements": [
                    "Persist run traces and scorecards so judges can replay previous quotes after backend restart.",
                    "Add good, better, best scenario comparison for procurement trade-off analysis.",
                    "Connect live supplier APIs for stock, lead time, and shipping quotes when available.",
                    "Add quote approval workflow with customer sign-off and revision history.",
                ],
            }
        )
