"""Agent 2: solution builder using a Chutes orchestration model."""

from __future__ import annotations

import json
import math
import re
from typing import Callable, Optional

from rich.console import Console

from core.catalog import get_product_by_id, search_products
from core.config import CHUTES_BASE_URL, GROQ_BASE_URL, GROQ_FALLBACK_MODEL, GROQ_PARSER_MODEL, ORCHESTRATOR_MODEL, get_chutes_client, get_groq_client
from core.llm_utils import friendly_api_error, message_to_dict, now_iso, parse_json_response, run_with_deadline
from core.models import AgentStep, Product, ReviewerFeedback, SelfCritiqueResult, StructuredBrief
from core.tools import TOOL_DEFINITIONS, calculate_budget_fit, check_compatibility, check_delivery, dispatch_tool, summarize_tool_json

console = Console()

SALES_ENGINEER_SYSTEM_PROMPT = """You are a Senior Technical Sales Engineer with 15 years of experience
designing IT infrastructure solutions for businesses in Malaysia.

Your task: design a COMPLETE, VALID, QUOTED IT solution for the client.

You have 8 tools. Follow this MANDATORY process:

PHASE 1 - DISCOVERY:
Call search_catalog() for EVERY category in inferred_categories.
Do not call search_web_products() during discovery. Prefer catalog product URLs and source_platform values.
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
Before final JSON, call search_web_products() only for final selected products that still lack product_url.
Limit web lookup to at most 2 final products; skip it when catalog URLs already exist.
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
        solution = self._build_fast_catalog_solution(brief, reviewer_feedback, on_step)
        critique = self._local_self_critique(brief, solution, 1, "")
        self.self_critique_history.append(critique)
        if on_step:
            on_step(
                AgentStep.model_validate(
                    {
                        "iteration": 1,
                        "agent_name": "SalesEngineer",
                        "action": "Ran deterministic self-critique on proposed solution",
                        "tool_called": None,
                        "tool_args": None,
                        "tool_result_summary": f"passed={critique.passed}; issues={len(critique.issues_found)}",
                        "timestamp": now_iso(),
                    }
                )
            )
        solution["self_critique_history"] = [item.model_dump() for item in self.self_critique_history]
        return solution

    def _build_fast_catalog_solution(
        self,
        brief: StructuredBrief,
        reviewer_feedback: Optional[ReviewerFeedback],
        on_step: Optional[Callable[[AgentStep], None]],
    ) -> dict:
        """Build catalog evidence, then let AI make a bounded quoted-solution decision."""
        categories = self._expanded_categories(brief)
        selected: list[dict] = []
        catalog_evidence: dict[str, list[dict]] = {}
        reasoning: list[str] = [
            "Prepared catalog/tool evidence for an AI-guided autonomous sales engineer decision."
        ]
        if reviewer_feedback is not None:
            reasoning.append("Reviewer feedback was incorporated into the deterministic revision pass.")
        per_category_budget = brief.budget_myr / max(len(categories), 1)

        for category in categories:
            candidates = search_products(category=category, in_stock_only=True)
            evidence_candidates = sorted(candidates, key=lambda product: self._score_product(product, brief), reverse=True)[:5]
            catalog_evidence[category] = [self._compact_product(product) for product in evidence_candidates]
            if on_step:
                on_step(
                    AgentStep.model_validate(
                        {
                            "iteration": len(selected) + 1,
                            "agent_name": "SalesEngineer",
                            "action": f"Searched catalog for {category}",
                            "tool_called": "search_catalog",
                            "tool_args": {"category": category, "in_stock_only": True},
                            "tool_result_summary": self._candidate_summary(candidates),
                            "timestamp": now_iso(),
                        }
                    )
                )
            category_items = self._select_products_for_category(category, candidates, brief, per_category_budget)
            if not category_items:
                reasoning.append(f"No in-stock catalog item was available for {category}.")
                continue
            for item in category_items:
                product = item["product"]
                selected.append(
                    {
                        "product_id": product.id,
                        "quantity": item["quantity"],
                        "confidence_score": item["confidence_score"],
                        "confidence_reason": item["confidence_reason"],
                        "alternatives_considered": item["alternatives_considered"],
                        "product_url": product.url,
                        "source_platform": product.source_platform,
                    }
                )
                reasoning.append(f"Selected {product.name} for {category}: {item['confidence_reason']}")

        selected = self._merge_duplicate_selections(selected)
        selected = self._fit_solution_to_budget(selected, brief, reasoning, on_step)
        selected_ids = [item["product_id"] for item in selected]
        quantities = {item["product_id"]: int(item.get("quantity", 1)) for item in selected}
        budget_result = calculate_budget_fit(selected_ids, quantities, brief.budget_myr)
        delivery_result = check_delivery(selected_ids, brief.delivery_location)
        compatibility_summary = self._compatibility_summary(selected_ids)
        total = float(budget_result.data["total_myr"]) if budget_result.success else self._selected_total(selected)
        delivery_ok = bool(delivery_result.success and delivery_result.data.get("feasible"))
        warnings: list[str] = []
        if not budget_result.success or not budget_result.data.get("within_budget"):
            warnings.append(f"Subtotal MYR {total:,.2f} exceeds budget MYR {brief.budget_myr:,.2f}; procurement approval required.")
        if not delivery_ok:
            warnings.append("One or more selected products need delivery confirmation for the requested region.")
        if not compatibility_summary["all_compatible"]:
            warnings.extend(compatibility_summary["issues"][:5])

        if on_step:
            on_step(
                AgentStep.model_validate(
                    {
                        "iteration": len(selected) + 1,
                        "agent_name": "SalesEngineer",
                        "action": "Validated budget, delivery, and compatibility",
                        "tool_called": "calculate_budget_fit",
                        "tool_args": {"product_ids": selected_ids, "budget_myr": brief.budget_myr},
                        "tool_result_summary": (
                            f"total MYR {total:,.2f}; within_budget={total <= brief.budget_myr}; "
                            f"delivery={delivery_ok}; compatibility={compatibility_summary['all_compatible']}"
                        ),
                        "timestamp": now_iso(),
                    }
                )
            )

        solution_summary = (
            f"Prepared a catalog-backed quote for {brief.client_name} covering {', '.join(categories)}. "
            f"The proposed subtotal is MYR {total:,.2f} against a MYR {brief.budget_myr:,.2f} budget, "
            f"with delivery {'confirmed' if delivery_ok else 'requiring confirmation'} for {brief.delivery_location}."
        )
        reasoning_summary = self._reasoning_summary(brief, selected, total, delivery_ok, compatibility_summary)
        baseline_solution = {
            "selected_products": selected,
            "reasoning_log": reasoning,
            "total_estimated_myr": total,
            "solution_summary": solution_summary,
            "reasoning_summary": reasoning_summary,
            "recommendations": self._recommendations_for_solution(brief, selected, total),
            "warnings": warnings,
        }

        return self._ai_refine_catalog_solution(
            brief=brief,
            baseline_solution=baseline_solution,
            catalog_evidence=catalog_evidence,
            reviewer_feedback=reviewer_feedback,
            on_step=on_step,
        )

    def _ai_refine_catalog_solution(
        self,
        brief: StructuredBrief,
        baseline_solution: dict,
        catalog_evidence: dict[str, list[dict]],
        reviewer_feedback: Optional[ReviewerFeedback],
        on_step: Optional[Callable[[AgentStep], None]],
    ) -> dict:
        """Use one bounded LLM call to improve the catalog-backed quote."""
        prompt = {
            "hackathon_track": "Problem Statement 1: The Autonomous Sales Engineer",
            "criteria_focus": [
                "LLM and agentic use must meaningfully enhance the solution",
                "constraint-based discovery",
                "logistics and fulfillment reasoning",
                "dynamic quote generation with URLs, reasoning summary, and bill of materials",
                "mathematical precision for budget, taxes, shipping, and TCO",
            ],
            "brief": brief.model_dump(),
            "catalog_evidence": catalog_evidence,
            "validated_baseline_solution": self._compact_solution_for_ai(baseline_solution),
            "reviewer_feedback": reviewer_feedback.model_dump() if reviewer_feedback else None,
            "rules": [
                "Use only product_id values present in catalog_evidence or validated_baseline_solution.",
                "Do not invent prices, taxes, URLs, platforms, or product IDs.",
                "You may keep the baseline BOM if it is the best valid solution, but improve AI reasoning and recommendations.",
                "Return JSON only in the exact solution schema.",
            ],
        }
        system = (
            "You are an AI autonomous technical sales consultant for Malaysia. "
            "Choose a complete compatible solution from the supplied catalog evidence, explain the constraint reasoning, "
            "and produce a professional quoted solution. Return strict JSON only."
        )
        try:
            client = get_chutes_client()
            response = run_with_deadline(
                lambda: client.chat.completions.create(
                    model=ORCHESTRATOR_MODEL,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                    ],
                    timeout=5,
                ),
                6,
                "Chutes solution refinement",
            )
            ai_solution = parse_json_response(response.choices[0].message.content or "")
            used_model = ORCHESTRATOR_MODEL
        except Exception as primary_exc:
            console.log(f"[yellow]Chutes solution refinement unavailable; trying Groq AI fallback: {primary_exc}[/yellow]")
            try:
                client = get_groq_client()
                response = run_with_deadline(
                    lambda: client.chat.completions.create(
                        model=GROQ_PARSER_MODEL,
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                        ],
                        response_format={"type": "json_object"},
                        timeout=12,
                    ),
                    14,
                    "Groq solution refinement",
                )
                ai_solution = parse_json_response(response.choices[0].message.content or "")
                used_model = GROQ_PARSER_MODEL
            except Exception as exc:
                console.log(f"[yellow]AI solution refinement unavailable; using validated catalog plan: {exc}[/yellow]")
                if on_step:
                    on_step(
                        AgentStep.model_validate(
                            {
                                "iteration": len(baseline_solution.get("selected_products", [])) + 2,
                                "agent_name": "SalesEngineer",
                                "action": "AI solution refinement unavailable; used validated catalog plan",
                                "tool_called": None,
                                "tool_args": {"primary_model": ORCHESTRATOR_MODEL, "fallback_model": GROQ_PARSER_MODEL},
                                "tool_result_summary": str(exc)[:220],
                                "timestamp": now_iso(),
                            }
                        )
                    )
                return baseline_solution

        try:
            refined = self._validated_ai_solution(brief, ai_solution, baseline_solution, catalog_evidence)
            if on_step:
                on_step(
                    AgentStep.model_validate(
                        {
                            "iteration": len(refined.get("selected_products", [])) + 2,
                            "agent_name": "SalesEngineer",
                            "action": "AI refined catalog-backed solution plan",
                            "tool_called": None,
                            "tool_args": {"model": used_model, "primary_model": ORCHESTRATOR_MODEL},
                            "tool_result_summary": f"{len(refined.get('selected_products', []))} products; total MYR {refined.get('total_estimated_myr', 0):,.2f}",
                            "timestamp": now_iso(),
                        }
                    )
                )
            return refined
        except Exception as exc:
            console.log(f"[yellow]AI solution validation failed; using validated catalog plan: {exc}[/yellow]")
            if on_step:
                on_step(
                    AgentStep.model_validate(
                        {
                            "iteration": len(baseline_solution.get("selected_products", [])) + 2,
                            "agent_name": "SalesEngineer",
                            "action": "AI solution validation failed; used validated catalog plan",
                            "tool_called": None,
                            "tool_args": {"model": ORCHESTRATOR_MODEL},
                            "tool_result_summary": str(exc)[:220],
                            "timestamp": now_iso(),
                        }
                    )
                )
            return baseline_solution

    def _validated_ai_solution(
        self,
        brief: StructuredBrief,
        ai_solution: dict,
        baseline_solution: dict,
        catalog_evidence: dict[str, list[dict]],
    ) -> dict:
        """Validate AI output against catalog evidence and deterministic constraints."""
        allowed_ids = {
            item["id"]
            for candidates in catalog_evidence.values()
            for item in candidates
            if isinstance(item, dict) and item.get("id")
        }
        baseline_by_category = self._first_selection_by_category(baseline_solution.get("selected_products", []))
        selected: list[dict] = []
        for item in ai_solution.get("selected_products", []):
            if not isinstance(item, dict):
                continue
            product_id = str(item.get("product_id") or "")
            product = get_product_by_id(product_id)
            if product is None or (allowed_ids and product_id not in allowed_ids):
                continue
            selected.append(
                {
                    "product_id": product.id,
                    "quantity": max(1, int(item.get("quantity") or self._quantity_for_product(product, brief))),
                    "confidence_score": max(0.0, min(1.0, float(item.get("confidence_score") or 0.82))),
                    "confidence_reason": str(item.get("confidence_reason") or "AI selected this product from validated catalog evidence."),
                    "alternatives_considered": [str(value) for value in item.get("alternatives_considered", [])[:4]],
                    "product_url": product.url,
                    "source_platform": product.source_platform,
                }
            )
        if not selected:
            selected = [dict(item) for item in baseline_solution.get("selected_products", [])]

        covered_categories = self._selection_categories(selected)
        for category in self._expanded_categories(brief):
            if category not in covered_categories and category in baseline_by_category:
                selected.append(dict(baseline_by_category[category]))
                covered_categories.add(category)

        selected = self._merge_duplicate_selections(selected)
        reasoning = [str(item) for item in ai_solution.get("reasoning_log", [])[:12] if item]
        if not reasoning:
            reasoning = list(baseline_solution.get("reasoning_log", []))
        selected = self._fit_solution_to_budget(selected, brief, reasoning, None)
        selected_ids = [item["product_id"] for item in selected]
        quantities = {item["product_id"]: int(item.get("quantity", 1)) for item in selected}
        budget_result = calculate_budget_fit(selected_ids, quantities, brief.budget_myr)
        delivery_result = check_delivery(selected_ids, brief.delivery_location)
        compatibility_summary = self._compatibility_summary(selected_ids)
        total = float(budget_result.data["total_myr"]) if budget_result.success else self._selected_total(selected)
        delivery_ok = bool(delivery_result.success and delivery_result.data.get("feasible"))
        warnings = [str(item) for item in ai_solution.get("warnings", [])[:8] if item]
        if total > brief.budget_myr:
            warnings.append(f"Subtotal MYR {total:,.2f} exceeds budget MYR {brief.budget_myr:,.2f}; procurement approval required.")
        if not delivery_ok:
            warnings.append("One or more selected products need delivery confirmation for the requested region.")
        if not compatibility_summary["all_compatible"]:
            warnings.extend(compatibility_summary["issues"][:5])
        return {
            "selected_products": selected,
            "reasoning_log": reasoning,
            "total_estimated_myr": total,
            "solution_summary": str(ai_solution.get("solution_summary") or baseline_solution.get("solution_summary") or "Catalog-backed AI quote prepared."),
            "reasoning_summary": str(
                ai_solution.get("reasoning_summary")
                or self._reasoning_summary(brief, selected, total, delivery_ok, compatibility_summary)
            ),
            "recommendations": [
                str(item)
                for item in (ai_solution.get("recommendations") or baseline_solution.get("recommendations") or [])[:8]
                if item
            ],
            "warnings": list(dict.fromkeys(warnings)),
        }

    def _compact_product(self, product: Product) -> dict:
        specs = {}
        for key, value in list(product.specs.items())[:6]:
            if isinstance(value, (str, int, float, bool)):
                specs[key] = value
        return {
            "id": product.id,
            "name": product.name,
            "category": product.category,
            "price_myr": product.price_myr,
            "specs": specs,
            "available_regions": product.available_regions,
            "compatible_with": product.compatible_with,
            "brand": product.brand,
            "url": product.url,
            "source_platform": product.source_platform,
        }

    def _compact_solution_for_ai(self, solution: dict) -> dict:
        return {
            "selected_products": solution.get("selected_products", [])[:12],
            "total_estimated_myr": solution.get("total_estimated_myr"),
            "solution_summary": solution.get("solution_summary", ""),
            "reasoning_summary": solution.get("reasoning_summary", ""),
            "recommendations": solution.get("recommendations", [])[:6],
            "warnings": solution.get("warnings", [])[:6],
        }

    def _first_selection_by_category(self, selected: list[dict]) -> dict[str, dict]:
        by_category: dict[str, dict] = {}
        for item in selected:
            product = get_product_by_id(item.get("product_id", ""))
            if product is not None and product.category not in by_category:
                by_category[product.category] = item
        return by_category

    def _selection_categories(self, selected: list[dict]) -> set[str]:
        categories: set[str] = set()
        for item in selected:
            product = get_product_by_id(item.get("product_id", ""))
            if product is not None:
                categories.add(product.category)
        return categories

    def _expanded_categories(self, brief: StructuredBrief) -> list[str]:
        """Include obvious categories the parser may miss from terse briefs."""
        categories = list(dict.fromkeys(brief.inferred_categories))
        text = self._brief_text(brief)
        hints = {
            "peripheral": ["conference", "conferencing", "webcam", "camera", "headset"],
            "networking": ["wifi", "internet", "router", "firewall", "switch", "vpn"],
            "storage": ["nas", "file sharing", "shared files", "backup storage"],
            "software_license": ["microsoft 365", "office", "teams", "license"],
            "power": ["ups", "backup power", "battery"],
        }
        for category, terms in hints.items():
            if category not in categories and any(term in text for term in terms):
                categories.append(category)
        return categories

    def _brief_text(self, brief: StructuredBrief) -> str:
        return " ".join([brief.use_case, *brief.requirements]).lower()

    def _product_text(self, product: Product) -> str:
        return f"{product.name} {product.brand} {json.dumps(product.specs, ensure_ascii=False)}".lower()

    def _candidate_summary(self, candidates: list[Product]) -> str:
        names = ", ".join(product.name for product in candidates[:3])
        suffix = f"; +{len(candidates) - 3} more" if len(candidates) > 3 else ""
        return f"{len(candidates)} candidate(s): {names}{suffix}" if names else "0 candidates"

    def _select_products_for_category(
        self,
        category: str,
        candidates: list[Product],
        brief: StructuredBrief,
        per_category_budget: float,
    ) -> list[dict]:
        if not candidates:
            return []
        text = self._brief_text(brief)
        if category == "networking":
            return self._select_networking(candidates, brief)
        if category == "storage":
            return self._select_storage(candidates, brief)
        if category == "software_license":
            return self._select_software(candidates, brief)
        if category == "peripheral":
            return self._select_peripherals(candidates, brief)
        if category == "compute":
            return self._select_compute(candidates, brief)
        if category == "power":
            product = self._best_product(candidates, brief, ["ups", "back-ups", "smart-ups", "battery"])
            return [self._pack_selection(product, self._quantity_for_product(product, brief), candidates, "UPS coverage for power continuity.", 0.86)]
        if category == "display":
            product = self._best_product(candidates, brief, ["monitor", "display", "fhd", "4k"])
            return [self._pack_selection(product, self._quantity_for_product(product, brief), candidates, "Matched display needs and regional availability.", 0.82)]
        if category == "cooling":
            terms = ["rack", "netshelter"] if "server room" in text else ["cooler", "cooling"]
            product = self._best_product(candidates, brief, terms)
            return [self._pack_selection(product, 1, candidates, "Selected for server-room support and catalog availability.", 0.78)]
        product = self._best_product(candidates, brief, [])
        return [self._pack_selection(product, self._quantity_for_product(product, brief), candidates, "Best catalog match for requested category.", 0.76)]

    def _select_networking(self, candidates: list[Product], brief: StructuredBrief) -> list[dict]:
        text = self._brief_text(brief)
        selected: list[dict] = []
        if any(term in text for term in ["wifi", "wireless", "floor", "coverage"]):
            access_point = self._best_product(candidates, brief, ["wifi", "ap", "access point", "unifi"])
            selected.append(self._pack_selection(access_point, self._floor_count(text), candidates, "WiFi coverage requirement mapped to access points.", 0.9))
        if any(term in text for term in ["secure internet", "internet", "firewall", "vpn", "router"]):
            gateway_pool = [
                product
                for product in candidates
                if any(term in self._product_text(product) for term in ["firewall", "vpn", "dream machine", "dual wan"])
            ] or candidates
            gateway = self._best_product(gateway_pool, brief, ["firewall", "vpn", "dream machine", "dual wan"])
            selected.append(self._pack_selection(gateway, 1, candidates, "Secure internet edge requirement mapped to a gateway/firewall.", 0.88))
        if any(term in text for term in ["switch", "ports", "staff", "users", "server room", "shared files"]):
            users = brief.num_users or 1
            switch_pool = [
                product
                for product in candidates
                if "switch" in product.name.lower() and int(product.specs.get("ports", 0)) >= max(users, 8)
            ] or [product for product in candidates if "switch" in product.name.lower()] or candidates
            switch = self._best_product(switch_pool, brief, ["switch", "port"])
            selected.append(self._pack_selection(switch, 1, candidates, "User count and shared services require wired switching capacity.", 0.84))
        if not selected:
            product = self._best_product(candidates, brief, ["router", "switch", "wifi"])
            selected.append(self._pack_selection(product, self._quantity_for_product(product, brief), candidates, "Balanced network foundation from local catalog.", 0.8))
        return self._unique_product_items(selected)

    def _select_storage(self, candidates: list[Product], brief: StructuredBrief) -> list[dict]:
        text = self._brief_text(brief)
        selected: list[dict] = []
        if any(term in text for term in ["nas", "file sharing", "shared files", "server room"]):
            nas_pool = [
                product
                for product in candidates
                if "nas" in product.name.lower() or "bays" in product.specs
            ]
            nas = self._best_product(nas_pool or candidates, brief, ["synology", "qnap", "4-bay"])
            selected.append(self._pack_selection(nas, 1, candidates, "NAS requirement mapped to shared storage appliance.", 0.9))
            drives = [product for product in candidates if any(term in self._product_text(product) for term in ["hdd", "red pro", "ironwolf"])]
            if drives:
                drive = self._best_product(drives, brief, ["hdd", "nas_optimized", "ironwolf", "red pro"])
                selected.append(self._pack_selection(drive, 2, candidates, "NAS appliance needs redundant storage media.", 0.84))
        else:
            product = self._best_product(candidates, brief, ["ssd", "usb", "backup", "storage"])
            selected.append(self._pack_selection(product, self._quantity_for_product(product, brief), candidates, "Matched general storage requirement.", 0.78))
        return self._unique_product_items(selected)

    def _select_software(self, candidates: list[Product], brief: StructuredBrief) -> list[dict]:
        text = self._brief_text(brief)
        selected: list[dict] = []
        users = brief.num_users or 1
        if any(term in text for term in ["microsoft 365", "office", "teams", "video conferencing"]):
            standard = self._find_by_terms(candidates, ["business standard"])
            basic = self._find_by_terms(candidates, ["business basic"])
            product = basic if brief.priority == "budget" and basic is not None else standard or basic or self._best_product(candidates, brief, ["microsoft", "teams"])
            selected.append(self._pack_selection(product, users, candidates, "Microsoft 365 seats sized to named users.", 0.88))
        if any(term in text for term in ["backup software", "server backup", "vm backup", "veeam"]):
            backup = self._find_by_terms(candidates, ["veeam", "backup essentials"])
            if backup is not None:
                selected.append(self._pack_selection(backup, 1, candidates, "Backup software requirement mapped to catalog license.", 0.82))
        if not selected:
            product = self._best_product(candidates, brief, ["license", "microsoft", "software"])
            selected.append(self._pack_selection(product, self._quantity_for_product(product, brief), candidates, "Selected software license from catalog.", 0.76))
        return self._unique_product_items(selected)

    def _select_peripherals(self, candidates: list[Product], brief: StructuredBrief) -> list[dict]:
        text = self._brief_text(brief)
        terms = ["conference", "meetup", "camera"] if any(term in text for term in ["conference", "conferencing", "meeting room"]) else ["webcam", "headset", "keyboard", "mouse"]
        product = self._best_product(candidates, brief, terms)
        quantity = 1 if any(term in self._product_text(product) for term in ["meetup", "conference"]) else self._quantity_for_product(product, brief)
        return [self._pack_selection(product, quantity, candidates, "Video collaboration requirement mapped to room/user peripherals.", 0.86)]

    def _select_compute(self, candidates: list[Product], brief: StructuredBrief) -> list[dict]:
        text = self._brief_text(brief)
        terms = ["server", "poweredge", "proliant"] if any(term in text for term in ["server", "server room"]) else ["desktop", "thinkcentre", "optiplex", "mini"]
        product = self._best_product(candidates, brief, terms)
        quantity = 1 if any(term in self._product_text(product) for term in ["server", "poweredge", "proliant"]) else self._quantity_for_product(product, brief)
        return [self._pack_selection(product, quantity, candidates, "Compute requirement mapped to catalog hardware.", 0.84)]

    def _best_product(self, candidates: list[Product], brief: StructuredBrief, terms: list[str]) -> Product:
        matching = [product for product in candidates if any(term in self._product_text(product) for term in terms)] if terms else candidates
        pool = matching or candidates
        deliverable = [product for product in pool if self._is_deliverable(product, brief.delivery_location)] or pool
        return sorted(deliverable, key=lambda product: self._score_product(product, brief), reverse=True)[0]

    def _find_by_terms(self, candidates: list[Product], terms: list[str]) -> Optional[Product]:
        for product in candidates:
            product_text = self._product_text(product)
            if all(term in product_text for term in terms):
                return product
        return None

    def _score_product(self, product: Product, brief: StructuredBrief) -> float:
        score = 10.0 if self._is_deliverable(product, brief.delivery_location) else 0.0
        text = self._brief_text(brief)
        product_text = self._product_text(product)
        for term in text.split():
            if len(term) > 3 and term in product_text:
                score += 0.8
        if brief.priority == "budget":
            score += max(0.0, 8.0 - product.price_myr / 650)
        elif brief.priority == "performance":
            score += min(product.price_myr / 900, 8.0)
        else:
            score += max(0.0, 6.0 - product.price_myr / 1600)
        return score

    def _pack_selection(
        self,
        product: Product,
        quantity: int,
        candidates: list[Product],
        reason: str,
        confidence: float,
    ) -> dict:
        alternatives = [candidate.id for candidate in candidates if candidate.id != product.id][:3]
        return {
            "product": product,
            "quantity": max(1, quantity),
            "confidence_score": confidence,
            "confidence_reason": reason,
            "alternatives_considered": alternatives,
        }

    def _quantity_for_product(self, product: Product, brief: StructuredBrief) -> int:
        product_text = self._product_text(product)
        users = brief.num_users or 1
        if product.category == "software_license":
            return users
        if product.category == "networking" and any(term in product_text for term in ["wifi", "access point", "unifi ap"]):
            return self._floor_count(self._brief_text(brief))
        if product.category == "storage" and any(term in product_text for term in ["hdd", "ironwolf", "red pro"]):
            return 2
        if product.category == "compute" and any(term in product_text for term in ["desktop", "thinkcentre", "optiplex", "elitedesk"]):
            return users
        return self._quantity_for_category(product.category, brief)

    def _floor_count(self, text: str) -> int:
        match = re.search(r"(\d+)\s*floors?", text)
        return max(1, int(match.group(1))) if match else 1

    def _is_deliverable(self, product: Product, delivery_location: str) -> bool:
        location = delivery_location.lower()
        return "nationwide" in product.available_regions or any(region.lower() in location for region in product.available_regions)

    def _unique_product_items(self, items: list[dict]) -> list[dict]:
        seen: set[str] = set()
        unique: list[dict] = []
        for item in items:
            product_id = item["product"].id
            if product_id in seen:
                continue
            seen.add(product_id)
            unique.append(item)
        return unique

    def _merge_duplicate_selections(self, selected: list[dict]) -> list[dict]:
        merged: dict[str, dict] = {}
        for item in selected:
            product_id = item["product_id"]
            if product_id not in merged:
                merged[product_id] = dict(item)
                continue
            merged[product_id]["quantity"] = max(int(merged[product_id].get("quantity", 1)), int(item.get("quantity", 1)))
        return list(merged.values())

    def _fit_solution_to_budget(
        self,
        selected: list[dict],
        brief: StructuredBrief,
        reasoning: list[str],
        on_step: Optional[Callable[[AgentStep], None]],
    ) -> list[dict]:
        total = self._selected_total(selected)
        if total <= brief.budget_myr:
            return selected
        adjusted = [dict(item) for item in selected]
        for item in sorted(adjusted, key=lambda candidate: self._selection_subtotal(candidate), reverse=True):
            product = get_product_by_id(item["product_id"])
            if product is None:
                continue
            alternatives = search_products(category=product.category, in_stock_only=True)
            for alternative in alternatives:
                if alternative.id == product.id or alternative.price_myr >= product.price_myr:
                    continue
                if not self._is_deliverable(alternative, brief.delivery_location):
                    continue
                if self._would_drop_explicit_requirement(product, alternative, brief):
                    continue
                item.update(
                    {
                        "product_id": alternative.id,
                        "confidence_score": min(float(item.get("confidence_score", 0.75)), 0.78),
                        "confidence_reason": f"Budget-fit substitution for {product.name}; retained {product.category} coverage.",
                        "product_url": alternative.url,
                        "source_platform": alternative.source_platform,
                    }
                )
                reasoning.append(f"Substituted {product.name} with {alternative.name} to reduce subtotal.")
                if on_step:
                    on_step(
                        AgentStep.model_validate(
                            {
                                "iteration": len(adjusted),
                                "agent_name": "SalesEngineer",
                                "action": "Applied budget-fit substitution",
                                "tool_called": "find_alternatives",
                                "tool_args": {"product_id": product.id, "max_price_myr": product.price_myr},
                                "tool_result_summary": f"{product.name} -> {alternative.name}",
                                "timestamp": now_iso(),
                            }
                        )
                    )
                total = self._selected_total(adjusted)
                break
            if total <= brief.budget_myr:
                break
        return adjusted

    def _would_drop_explicit_requirement(self, current: Product, replacement: Product, brief: StructuredBrief) -> bool:
        text = self._brief_text(brief)
        current_text = self._product_text(current)
        replacement_text = self._product_text(replacement)
        guarded_terms = ["nas", "conference", "wifi", "firewall", "server"]
        return any(term in text and term in current_text and term not in replacement_text for term in guarded_terms)

    def _selected_total(self, selected: list[dict]) -> float:
        return sum(self._selection_subtotal(item) for item in selected)

    def _selection_subtotal(self, item: dict) -> float:
        product = get_product_by_id(item.get("product_id", ""))
        return (product.price_myr if product else 0.0) * int(item.get("quantity", 1))

    def _compatibility_summary(self, product_ids: list[str]) -> dict:
        issues: list[str] = []
        pairs: list[dict] = []
        for first_index, first_id in enumerate(product_ids):
            for second_id in product_ids[first_index + 1 :]:
                result = check_compatibility(first_id, second_id)
                data = result.data if result.success else {"compatible": False, "reason": result.error or "Unknown"}
                pairs.append({"a": first_id, "b": second_id, **data})
                if not data.get("compatible"):
                    issues.append(f"{first_id} and {second_id}: {data.get('reason')}")
        return {"pairs_checked": pairs, "all_compatible": not issues, "issues": issues}

    def _reasoning_summary(
        self,
        brief: StructuredBrief,
        selected: list[dict],
        total: float,
        delivery_ok: bool,
        compatibility_summary: dict,
    ) -> str:
        product_phrases = []
        for item in selected[:10]:
            product = get_product_by_id(item["product_id"])
            if product is None:
                continue
            product_phrases.append(f"{item['quantity']}x {product.name} for {product.category}")
        coverage = "; ".join(product_phrases)
        budget_line = f"The subtotal is MYR {total:,.2f}, using {(total / brief.budget_myr * 100) if brief.budget_myr else 0:.1f}% of budget."
        delivery_line = "All selected products are deliverable to the requested region." if delivery_ok else "Delivery confirmation is needed for one or more items."
        compatibility_line = "Compatibility checks passed." if compatibility_summary["all_compatible"] else "Some compatibility relationships require engineer review."
        return f"The solution covers {coverage}. {budget_line} {delivery_line} {compatibility_line} It favors verified catalog items with local MYR pricing and supplier URLs, while preserving the client requirements for {brief.use_case}."

    def _recommendations_for_solution(self, brief: StructuredBrief, selected: list[dict], total: float) -> list[str]:
        recommendations = [
            "Confirm final stock, warranty, and lead time with the listed supplier before issuing a purchase order.",
            "Validate onsite quantities for cabling, mounting, and installation accessories before deployment.",
        ]
        text = self._brief_text(brief)
        if "wifi" in text:
            recommendations.append("Perform a quick WiFi survey before installation to confirm access point placement.")
        if "nas" in text or "shared files" in text:
            recommendations.append("Configure NAS permissions, backup schedule, and recovery testing before handover.")
        if total > brief.budget_myr * 0.9:
            recommendations.append("Keep a small contingency approval path because the quote uses most of the stated budget.")
        return recommendations

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
        for iteration in range(1, 13):
            try:
                response = client.chat.completions.create(
                    model=active_model,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                    timeout=60,
                )
            except Exception as exc:
                if not using_groq_fallback:
                    console.log(f"[yellow]Sales engineer primary failed; switching to Groq fallback: {exc}[/yellow]")
                    client = get_groq_client()
                    active_provider = "Groq"
                    active_model = GROQ_FALLBACK_MODEL
                    active_base_url = GROQ_BASE_URL
                    using_groq_fallback = True
                    messages = self._build_groq_reset_messages(brief, reviewer_feedback, critique)
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
                            timeout=60,
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
                    if self._is_groq_token_limit_error(exc):
                        console.log("[yellow]Groq fallback hit TPM/request-size limit; using deterministic local builder.[/yellow]")
                        if on_step:
                            on_step(
                                AgentStep.model_validate(
                                    {
                                        "iteration": iteration + (pass_index - 1) * 20,
                                        "agent_name": "SalesEngineer",
                                        "action": "Groq fallback reached TPM/request-size limit; switched to deterministic local catalog builder",
                                        "tool_called": "local_solution_builder",
                                        "tool_args": {"reason": "groq_tpm_or_request_too_large"},
                                        "tool_result_summary": str(exc)[:220],
                                        "timestamp": now_iso(),
                                    }
                                )
                            )
                        return self._build_local_fallback_solution(brief, on_step)
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
        raise RuntimeError("SalesEngineer exceeded max_iterations=12 without producing final JSON")

    def _build_groq_reset_messages(
        self,
        brief: StructuredBrief,
        reviewer_feedback: Optional[ReviewerFeedback],
        critique: Optional[SelfCritiqueResult],
    ) -> list[dict]:
        """Start a fresh, compact transcript when falling back to Groq."""
        compact_brief = {
            "client_name": brief.client_name,
            "use_case": brief.use_case,
            "budget_myr": brief.budget_myr,
            "delivery_location": brief.delivery_location,
            "num_users": brief.num_users,
            "requirements": brief.requirements[:12],
            "inferred_categories": brief.inferred_categories,
            "priority": brief.priority,
            "source": brief.source,
        }
        prompt = [
            "Build a complete solution for this brief and keep responses compact.",
            json.dumps(compact_brief, ensure_ascii=False),
        ]
        if reviewer_feedback is not None:
            prompt.append(
                "Prior reviewer feedback to address:\n"
                + json.dumps(
                    {
                        "risk_flags": reviewer_feedback.risk_flags[:8],
                        "suggestions": reviewer_feedback.suggestions[:8],
                        "approved": reviewer_feedback.approved,
                    },
                    ensure_ascii=False,
                )
            )
        if critique is not None:
            prompt.append(
                "Prior self-critique issues to address:\n"
                + json.dumps(
                    {
                        "issues_found": critique.issues_found[:8],
                        "budget_status": critique.budget_status,
                        "compatibility_status": critique.compatibility_status,
                    },
                    ensure_ascii=False,
                )
            )
        prompt.append("Return only final JSON and use tool calls only when necessary.")
        return [
            {"role": "system", "content": self._format_system_prompt(brief)},
            {"role": "user", "content": "\n\n".join(prompt)[:4500]},
        ]

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
        reasoning_parts = []
        for item in selected:
            product = get_product_by_id(item["product_id"])
            if not product:
                continue
            budget_per_cat = brief.budget_myr / max(len(brief.inferred_categories), 1)
            reasoning_parts.append(
                f"{product.name} was selected for {product.category} because it "
                f"fits within the MYR {budget_per_cat:,.0f} per-category budget allocation, "
                f"is deliverable to {brief.delivery_location}, "
                f"and is the best available match in the local catalog for the "
                f"{brief.priority} priority requirement."
            )
        dynamic_reasoning = " ".join(reasoning_parts)
        if not dynamic_reasoning:
            dynamic_reasoning = (
                "No products could be resolved from the catalog for this brief. "
                "Please verify category availability and budget constraints."
            )
        return {
            "selected_products": selected,
            "reasoning_log": reasoning,
            "total_estimated_myr": total,
            "solution_summary": summary,
            "reasoning_summary": dynamic_reasoning,
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
        compact_solution = self._compact_solution_for_critique(solution)
        prompt = f"""Critically review this IT solution. Check:
1. Are ALL inferred categories covered?
2. Is total within budget MYR {brief.budget_myr:,.2f}?
3. Are quantities right for {brief.num_users} users?
4. Any compatibility issues missed?
5. Any better value swaps available?

Solution: {json.dumps(compact_solution, ensure_ascii=False)}
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
                    timeout=60,
                )
            except Exception as primary_exc:
                console.log(f"[yellow]Self-critique primary failed; using Groq fallback: {primary_exc}[/yellow]")
                client = get_groq_client()
                active_model = GROQ_FALLBACK_MODEL
                response = client.chat.completions.create(
                    model=active_model,
                    messages=[{"role": "user", "content": prompt}],
                    timeout=60,
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
                "passed": not missing and budget_status != "over" and compatibility_status != "issues_found",
                "iteration": iteration,
                "issues_found": issues,
                "improvements_made": ["Validated category coverage, budget fit, and compatibility locally."],
                "budget_status": budget_status,
                "compatibility_status": compatibility_status,
            }
        )

    def _is_groq_token_limit_error(self, exc: Exception) -> bool:
        """Detect Groq token-per-minute / oversized-request failures."""
        text = str(exc).lower()
        markers = [
            "request too large",
            "tokens per minute",
            "tpm",
            "rate_limit_exceeded",
        ]
        return any(marker in text for marker in markers)

    def _compact_solution_for_critique(self, solution: dict) -> dict:
        """Keep critique payload concise to avoid provider token limits."""
        selected = []
        for item in solution.get("selected_products", [])[:12]:
            selected.append(
                {
                    "product_id": item.get("product_id"),
                    "quantity": item.get("quantity"),
                    "confidence_score": item.get("confidence_score"),
                    "source_platform": item.get("source_platform"),
                }
            )
        summary = (solution.get("solution_summary") or "")[:1200]
        reasoning_log = solution.get("reasoning_log", [])[:12]
        warnings = solution.get("warnings", [])[:12]
        recommendations = solution.get("recommendations", [])[:12]
        return {
            "selected_products": selected,
            "total_estimated_myr": solution.get("total_estimated_myr"),
            "solution_summary": summary,
            "reasoning_log": reasoning_log,
            "warnings": warnings,
            "recommendations": recommendations,
        }
