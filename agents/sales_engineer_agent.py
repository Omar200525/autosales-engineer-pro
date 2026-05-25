"""Agent 2: solution builder using Chutes Qwen 2.5 72B."""

from __future__ import annotations

import json
import math
from typing import Callable, Optional

from rich.console import Console

from core.catalog import get_product_by_id, search_products
from core.config import CHUTES_BASE_URL, GROQ_BASE_URL, GROQ_FALLBACK_MODEL, ORCHESTRATOR_MODEL, get_chutes_client, get_groq_client
from core.llm_utils import friendly_api_error, message_to_dict, now_iso, parse_json_response
from core.models import AgentStep, ReviewerFeedback, SelfCritiqueResult, StructuredBrief
from core.tools import TOOL_DEFINITIONS, calculate_budget_fit, check_compatibility, check_delivery, dispatch_tool, summarize_tool_json

console = Console()

SALES_ENGINEER_SYSTEM_PROMPT = """You are a Senior Technical Sales Engineer with 15 years of experience
designing IT infrastructure solutions for businesses in Malaysia.

Your task: design a COMPLETE, VALID, QUOTED IT solution for the client.

You have 7 tools. Follow this MANDATORY process:

PHASE 1 - DISCOVERY:
Call search_catalog() for EVERY category in inferred_categories.
Also call search_web_products() for major selected product types to capture real web product URLs when possible.
Use price filters based on priority:
  budget -> max_price = budget_myr * 0.25 per category
  performance -> no max_price filter
  balanced -> max_price = budget_myr * 0.35 per category

PHASE 2 - SELECTION:
For each category, select the best product using get_product_details().
Consider: requirements match, price, region availability.
Track alternatives_considered for each selection.

PHASE 3 - COMPATIBILITY:
Call check_compatibility() for EVERY unique pair of selected products.
If incompatible: call find_alternatives(), select replacement, recheck.
Do NOT finalize until ALL pairs pass.

PHASE 4 - BUDGET:
Call calculate_budget_fit() with all selections and quantities.
If over budget: find cheaper alternatives with find_alternatives().
If utilization < 60%: consider upgrading key components.
Target utilization: 75%-95%.

PHASE 5 - DELIVERY:
Call check_delivery() for all products to client's region.
If any product not deliverable: find_alternatives() in same category.

PHASE 6 - FINALIZE:
Only when ALL checks pass, return your final answer as JSON:
{
  "selected_products": [
    {
      "product_id": str,
      "quantity": int,
      "confidence_score": float,
      "confidence_reason": str,
      "alternatives_considered": [list of product_ids],
      "product_url": str,
      "source_platform": str
    }
  ],
  "reasoning_log": [list of decision strings],
  "total_estimated_myr": float,
  "solution_summary": str,
  "reasoning_summary": "150-200 words explaining why each major component was chosen, including compatibility, budget fit, and use case match",
  "recommendations": [list of strings],
  "warnings": [list of strings]
}"""


class SalesEngineerAgent:
    """Builds a quoted IT solution with tool calls and self-critique."""

    def __init__(self) -> None:
        """Initialize runtime state."""
        self.self_critique_history: list[SelfCritiqueResult] = []

    def build_solution(
        self,
        brief: StructuredBrief,
        reviewer_feedback: Optional[ReviewerFeedback] = None,
        on_step: Optional[Callable[[AgentStep], None]] = None,
    ) -> dict:
        """Build a complete product solution for the structured brief."""
        self.self_critique_history = []
        solution = self._run_main_loop(brief, reviewer_feedback, None, on_step, pass_index=1)
        for iteration in range(1, 4):
            critique = self._self_critique(brief, solution, iteration)
            self.self_critique_history.append(critique)
            if on_step:
                on_step(
                    AgentStep.model_validate(
                        {
                            "iteration": iteration,
                            "agent_name": "SalesEngineer",
                            "action": "Ran self-critique on proposed solution",
                            "tool_called": None,
                            "tool_args": None,
                            "tool_result_summary": f"passed={critique.passed}; issues={len(critique.issues_found)}",
                            "timestamp": now_iso(),
                        }
                    )
                )
            if critique.passed:
                break
            solution = self._run_main_loop(brief, reviewer_feedback, critique, on_step, pass_index=iteration + 1)
        solution["self_critique_history"] = [item.model_dump() for item in self.self_critique_history]
        return solution

    def _format_system_prompt(self, brief: StructuredBrief) -> str:
        return (
            SALES_ENGINEER_SYSTEM_PROMPT
            + "\n\nCLIENT:\n"
            + f"Location: {brief.delivery_location}\n"
            + f"Budget: MYR {brief.budget_myr:,.2f}\n"
            + f"Priority: {brief.priority}\n"
            + f"Users: {brief.num_users or 'not specified'}\n"
            + f"Categories: {', '.join(brief.inferred_categories)}"
        )

    def _initial_user_content(
        self,
        brief: StructuredBrief,
        reviewer_feedback: Optional[ReviewerFeedback],
        critique: Optional[SelfCritiqueResult],
    ) -> str:
        parts = [f"Build a complete solution for this brief:\n{brief.model_dump_json()}"]
        if reviewer_feedback is not None:
            parts.insert(
                0,
                "A senior reviewer rejected your previous solution.\n"
                f"Feedback:\n{reviewer_feedback.model_dump_json()}\nPlease revise.",
            )
        if critique is not None:
            parts.append(
                "Your own self-critique found issues. Revise accordingly:\n"
                f"{critique.model_dump_json()}"
            )
        return "\n\n".join(parts)

    def _run_main_loop(
        self,
        brief: StructuredBrief,
        reviewer_feedback: Optional[ReviewerFeedback],
        critique: Optional[SelfCritiqueResult],
        on_step: Optional[Callable[[AgentStep], None]],
        pass_index: int,
    ) -> dict:
        client = get_chutes_client()
        active_provider = "Chutes AI"
        active_model = ORCHESTRATOR_MODEL
        active_base_url = CHUTES_BASE_URL
        using_groq_fallback = False
        messages: list[dict] = [
            {"role": "system", "content": self._format_system_prompt(brief)},
            {"role": "user", "content": self._initial_user_content(brief, reviewer_feedback, critique)},
        ]
        for iteration in range(1, 21):
            try:
                response = client.chat.completions.create(
                    model=active_model,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                )
            except Exception as exc:
                if not using_groq_fallback:
                    console.log(f"[yellow]Sales engineer primary failed; switching to Groq fallback: {exc}[/yellow]")
                    client = get_groq_client()
                    active_provider = "Groq"
                    active_model = GROQ_FALLBACK_MODEL
                    active_base_url = GROQ_BASE_URL
                    using_groq_fallback = True
                    if on_step:
                        on_step(
                            AgentStep.model_validate(
                                {
                                    "iteration": iteration + (pass_index - 1) * 20,
                                    "agent_name": "SalesEngineer",
                                    "action": "Primary Chutes model failed; switched solution builder to Groq fallback",
                                    "tool_called": None,
                                    "tool_args": {"fallback_model": GROQ_FALLBACK_MODEL},
                                    "tool_result_summary": str(exc)[:220],
                                    "timestamp": now_iso(),
                                }
                            )
                        )
                    try:
                        response = client.chat.completions.create(
                            model=active_model,
                            messages=messages,
                            tools=TOOL_DEFINITIONS,
                            tool_choice="auto",
                        )
                    except Exception as fallback_exc:
                        console.log(f"[yellow]Groq tool fallback failed; using deterministic local builder: {fallback_exc}[/yellow]")
                        if on_step:
                            on_step(
                                AgentStep.model_validate(
                                    {
                                        "iteration": iteration + (pass_index - 1) * 20,
                                        "agent_name": "SalesEngineer",
                                        "action": "Groq fallback could not perform tool calls; used deterministic local catalog builder",
                                        "tool_called": "local_solution_builder",
                                        "tool_args": {"reason": "provider_tool_call_failure"},
                                        "tool_result_summary": str(fallback_exc)[:220],
                                        "timestamp": now_iso(),
                                    }
                                )
                            )
                        return self._build_local_fallback_solution(brief, on_step)
                else:
                    console.log(f"[red]Sales engineer fallback failed: {exc}[/red]")
                    raise friendly_api_error(active_provider, active_model, active_base_url, exc) from exc
            message = response.choices[0].message
            messages.append(message_to_dict(message))
            tool_calls = getattr(message, "tool_calls", None) or []
            if tool_calls:
                for tool_call in tool_calls:
                    function = tool_call.function
                    tool_name = function.name
                    try:
                        args = json.loads(function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    tool_json = dispatch_tool(tool_name, args)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_name,
                            "content": tool_json,
                        }
                    )
                    if on_step:
                        on_step(
                            AgentStep.model_validate(
                                {
                                    "iteration": iteration + (pass_index - 1) * 20,
                                    "agent_name": "SalesEngineer",
                                    "action": f"Dispatched tool call: {tool_name}",
                                    "tool_called": tool_name,
                                    "tool_args": args,
                                    "tool_result_summary": summarize_tool_json(tool_json),
                                    "timestamp": now_iso(),
                                }
                            )
                        )
                continue
            content = message.content or ""
            try:
                return parse_json_response(content)
            except Exception:
                messages.append({"role": "user", "content": "Respond ONLY with the final valid JSON object."})
        raise RuntimeError("SalesEngineer exceeded max_iterations=20 without producing final JSON")

    def _quantity_for_category(self, category: str, brief: StructuredBrief) -> int:
        """Estimate a sane quantity by category for deterministic fallback."""
        users = brief.num_users or 1
        if category == "software_license":
            return users
        if category == "display":
            return min(users, 20)
        if category == "peripheral":
            return min(users, 20)
        if category == "networking":
            return max(1, math.ceil(users / 25))
        return 1

    def _build_local_fallback_solution(
        self,
        brief: StructuredBrief,
        on_step: Optional[Callable[[AgentStep], None]],
    ) -> dict:
        """Build a valid quote from the local catalog when provider tool calling fails."""
        selected: list[dict] = []
        reasoning: list[str] = []
        per_category_budget = brief.budget_myr / max(len(brief.inferred_categories), 1)

        for category in brief.inferred_categories:
            max_price = None if brief.priority == "performance" else per_category_budget
            candidates = search_products(category=category, max_price=max_price, in_stock_only=True)
            if not candidates:
                candidates = search_products(category=category, in_stock_only=True)
            if not candidates:
                reasoning.append(f"No local catalog candidate found for {category}.")
                continue

            location = brief.delivery_location.lower()
            deliverable = [
                product
                for product in candidates
                if "nationwide" in product.available_regions
                or any(region.lower() in location for region in product.available_regions)
            ]
            pool = deliverable or candidates
            product = sorted(pool, key=lambda item: item.price_myr)[0]
            quantity = self._quantity_for_category(category, brief)
            selected.append(
                {
                    "product_id": product.id,
                    "quantity": quantity,
                    "confidence_score": 0.72 if deliverable else 0.62,
                    "confidence_reason": (
                        f"Selected from verified local catalog for {category}; "
                        f"optimized for {brief.priority} priority and delivery feasibility."
                    ),
                    "alternatives_considered": [item.id for item in pool[1:4]],
                    "product_url": product.url,
                    "source_platform": product.source_platform,
                }
            )
            reasoning.append(f"Selected {product.id} ({product.name}) for {category}.")
            if on_step:
                on_step(
                    AgentStep.model_validate(
                        {
                            "iteration": len(selected),
                            "agent_name": "SalesEngineer",
                            "action": f"Local fallback selected {product.name}",
                            "tool_called": "search_catalog",
                            "tool_args": {"category": category, "max_price_myr": max_price},
                            "tool_result_summary": f"{len(candidates)} candidates; selected {product.id}",
                            "timestamp": now_iso(),
                        }
                    )
                )

        product_ids = [item["product_id"] for item in selected]
        quantities = {item["product_id"]: item["quantity"] for item in selected}
        budget_result = calculate_budget_fit(product_ids, quantities, brief.budget_myr)
        delivery_result = check_delivery(product_ids, brief.delivery_location)
        compatible = True
        for index, first in enumerate(product_ids):
            for second in product_ids[index + 1 :]:
                result = check_compatibility(first, second)
                compatible = compatible and bool(result.success and result.data.get("compatible"))

        total = budget_result.data["total_myr"] if budget_result.success else sum(
            (get_product_by_id(item["product_id"]).price_myr if get_product_by_id(item["product_id"]) else 0)
            * item["quantity"]
            for item in selected
        )
        delivery_ok = bool(delivery_result.success and delivery_result.data.get("feasible"))
        summary = (
            f"Built a provider-resilient fallback quote for {brief.client_name} from the verified SQLite catalog. "
            f"The solution covers {', '.join(brief.inferred_categories)} with catalog-backed product IDs, "
            f"a subtotal of MYR {total:,.2f}, delivery status {'feasible' if delivery_ok else 'requiring review'}, "
            f"and compatibility {'verified' if compatible else 'requiring review'}."
        )
        return {
            "selected_products": selected,
            "reasoning_log": reasoning,
            "total_estimated_myr": total,
            "solution_summary": summary,
            "reasoning_summary": (
                "The automated fallback selected real products from the seeded Malaysian IT catalog after the cloud "
                "solution-builder model failed to produce valid tool calls. Each major component was chosen by matching "
                "the inferred category to in-stock catalog candidates, prioritizing products under the per-category budget "
                "where possible, then preferring items deliverable to the requested location or available nationwide. "
                "This keeps the quote grounded in verified product IDs, prices, compatibility metadata, and delivery regions "
                "instead of hallucinated web listings. Quantities are estimated from the number of users: software licenses "
                "scale per user, networking scales by user count, and shared infrastructure such as storage and power is "
                "quoted as core site equipment. The result is deliberately conservative, budget-aware, and compatible with "
                "the rest of the reporting, tax, shipping, TCO, and reviewer pipeline."
            ),
            "recommendations": [
                "Validate final quantities with the customer before issuing a purchase order.",
                "Use the generated PDF as a budgetary quote and confirm vendor stock before procurement.",
            ],
            "warnings": [
                "Cloud model tool-calling failed; this quote was generated by deterministic local fallback logic."
            ],
        }

    def _self_critique(
        self,
        brief: StructuredBrief,
        solution: dict,
        iteration: int,
    ) -> SelfCritiqueResult:
        client = get_chutes_client()
        active_model = ORCHESTRATOR_MODEL
        prompt = f"""Critically review this IT solution. Check:
1. Are ALL inferred categories covered?
2. Is total within budget MYR {brief.budget_myr:,.2f}?
3. Are quantities right for {brief.num_users} users?
4. Any compatibility issues missed?
5. Any better value swaps available?

Solution: {json.dumps(solution, ensure_ascii=False)}
Brief: {brief.model_dump_json()}

Respond ONLY with JSON:
{{
  "passed": bool,
  "issues_found": [list],
  "improvements_made": [list],
  "budget_status": "within"|"over"|"under_by_large_margin",
  "compatibility_status": "verified"|"issues_found"|"unresolved"
}}"""
        try:
            try:
                response = client.chat.completions.create(
                    model=active_model,
                    messages=[{"role": "user", "content": prompt}],
                )
            except Exception as primary_exc:
                console.log(f"[yellow]Self-critique primary failed; using Groq fallback: {primary_exc}[/yellow]")
                client = get_groq_client()
                active_model = GROQ_FALLBACK_MODEL
                response = client.chat.completions.create(
                    model=active_model,
                    messages=[{"role": "user", "content": prompt}],
                )
            data = parse_json_response(response.choices[0].message.content or "")
            data["iteration"] = iteration
            return SelfCritiqueResult.model_validate(data)
        except Exception as exc:
            console.log(f"[yellow]Self-critique provider failed; using local critique: {exc}[/yellow]")
            return self._local_self_critique(brief, solution, iteration, str(exc))

    def _local_self_critique(
        self,
        brief: StructuredBrief,
        solution: dict,
        iteration: int,
        provider_error: str,
    ) -> SelfCritiqueResult:
        """Create a deterministic self-critique when provider critique is unavailable."""
        selected = solution.get("selected_products", [])
        selected_categories = set()
        total = 0.0
        issues = []
        for item in selected:
            product = get_product_by_id(item.get("product_id", ""))
            if not product:
                issues.append(f"Unknown product ID: {item.get('product_id')}")
                continue
            selected_categories.add(product.category)
            total += product.price_myr * int(item.get("quantity", 1))
        missing = [category for category in brief.inferred_categories if category not in selected_categories]
        if missing:
            issues.append(f"Missing inferred categories: {', '.join(missing)}")
        budget_status = "within"
        if total > brief.budget_myr:
            issues.append(f"Subtotal MYR {total:,.2f} exceeds budget MYR {brief.budget_myr:,.2f}")
            budget_status = "over"
        elif total < brief.budget_myr * 0.6:
            budget_status = "under_by_large_margin"
        compatibility_status = "verified"
        ids = [item.get("product_id", "") for item in selected]
        for index, first in enumerate(ids):
            for second in ids[index + 1 :]:
                result = check_compatibility(first, second)
                if not (result.success and result.data.get("compatible")):
                    compatibility_status = "issues_found"
                    issues.append(f"Compatibility review needed for {first} and {second}")
        if provider_error:
            issues.append("Provider critique unavailable; local validation was used.")
        return SelfCritiqueResult.model_validate(
            {
                "passed": not missing and budget_status != "over",
                "iteration": iteration,
                "issues_found": issues,
                "improvements_made": ["Validated category coverage, budget fit, and compatibility locally."],
                "budget_status": budget_status,
                "compatibility_status": compatibility_status,
            }
        )
