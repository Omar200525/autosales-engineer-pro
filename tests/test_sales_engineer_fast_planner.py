"""Regression tests for the accelerated SalesEngineer planner."""

from __future__ import annotations

import json
from types import SimpleNamespace

from agents import sales_engineer_agent
from agents import parser_agent
from agents import reviewer_agent
from agents.parser_agent import ParserAgent
from agents.reviewer_agent import ReviewerAgent
from agents.sales_engineer_agent import SalesEngineerAgent
from core.catalog import get_product_by_id
from core.models import AgentStep, ReviewerFeedback, StructuredBrief
from pipeline import SalesEngineerPipeline


class _FakeCompletions:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(self.payload)))]
        )


class _FakeClient:
    def __init__(self, payload: dict) -> None:
        self.completions = _FakeCompletions(payload)
        self.chat = SimpleNamespace(completions=self.completions)


def _office_brief() -> StructuredBrief:
    return StructuredBrief.model_validate(
        {
            "client_name": "Acme KL Office",
            "use_case": "Small office setup for 15 staff with secure internet, WiFi, file sharing, Microsoft 365, and video conferencing.",
            "budget_myr": 25000,
            "delivery_location": "Kuala Lumpur",
            "num_users": 15,
            "requirements": [
                "WiFi coverage for 3 floors",
                "NAS for shared files",
                "UPS backup power",
                "Microsoft 365 for all users",
                "Video conferencing room setup",
            ],
            "inferred_categories": ["networking", "storage", "power", "software_license"],
            "priority": "balanced",
            "source": "text",
        }
    )


def test_ai_guided_planner_builds_complete_office_bom(monkeypatch) -> None:
    ai_payload = {
        "selected_products": [
            {"product_id": "prod_net_003", "quantity": 3, "confidence_score": 0.92, "confidence_reason": "AI selected access points for three floors.", "alternatives_considered": []},
            {"product_id": "prod_net_002", "quantity": 1, "confidence_score": 0.9, "confidence_reason": "AI selected secure gateway for internet edge.", "alternatives_considered": []},
            {"product_id": "prod_net_004", "quantity": 1, "confidence_score": 0.86, "confidence_reason": "AI selected 24-port switch for 15 users.", "alternatives_considered": []},
            {"product_id": "prod_sto_005", "quantity": 1, "confidence_score": 0.89, "confidence_reason": "AI selected NAS chassis for file sharing.", "alternatives_considered": []},
            {"product_id": "prod_sto_002", "quantity": 2, "confidence_score": 0.84, "confidence_reason": "AI selected NAS drives for redundancy.", "alternatives_considered": []},
            {"product_id": "prod_pwr_002", "quantity": 1, "confidence_score": 0.84, "confidence_reason": "AI selected UPS backup power.", "alternatives_considered": []},
            {"product_id": "prod_sft_001", "quantity": 15, "confidence_score": 0.88, "confidence_reason": "AI selected Microsoft 365 seats for all users.", "alternatives_considered": []},
            {"product_id": "prod_per_005", "quantity": 1, "confidence_score": 0.87, "confidence_reason": "AI selected room conferencing hardware.", "alternatives_considered": []},
        ],
        "reasoning_log": ["AI performed constraint-based catalog selection from validated evidence."],
        "total_estimated_myr": 23810,
        "solution_summary": "AI-guided catalog-backed office quote.",
        "reasoning_summary": "The AI selected a compatible office BOM covering WiFi, secure routing, switching, NAS storage, Microsoft 365, UPS, and conferencing while staying within budget.",
        "recommendations": ["Confirm stock and installation quantities before purchase."],
        "warnings": [],
    }
    fake_client = _FakeClient(ai_payload)

    monkeypatch.setattr(sales_engineer_agent, "get_chutes_client", lambda: fake_client)

    steps = []
    solution = SalesEngineerAgent().build_solution(_office_brief(), on_step=steps.append)
    products = [get_product_by_id(item["product_id"]) for item in solution["selected_products"]]
    categories = {product.category for product in products if product is not None}
    names = " ".join(product.name.lower() for product in products if product is not None)

    assert solution["total_estimated_myr"] <= 25000
    assert solution["warnings"] == []
    assert {"networking", "storage", "power", "software_license", "peripheral"}.issubset(categories)
    assert "nas" in names
    assert "microsoft 365" in names
    assert "meetup" in names
    assert fake_client.completions.calls == 1
    assert any(step.action == "AI refined catalog-backed solution plan" for step in steps)
    assert solution["self_critique_history"][0]["passed"] is True


def test_structured_parser_uses_ai_refinement(monkeypatch) -> None:
    ai_payload = {
        "client_name": "Acme KL Office",
        "use_case": "Office setup with WiFi, NAS, UPS, Microsoft 365, and video conferencing",
        "budget_myr": 25000,
        "delivery_location": "Kuala Lumpur",
        "num_users": 15,
        "requirements": [
            "WiFi coverage for 3 floors",
            "NAS for shared files",
            "UPS backup power",
            "Microsoft 365 for all users",
            "Video conferencing room setup",
        ],
        "inferred_categories": ["networking", "storage", "power", "software_license", "peripheral"],
        "priority": "balanced",
        "source": "text",
    }
    fake_client = _FakeClient(ai_payload)

    monkeypatch.setattr(parser_agent, "get_groq_client", lambda: fake_client)

    brief_text = """Client: Acme KL Office
Use case: Office setup with WiFi, NAS, UPS, Microsoft 365, and video conferencing
Budget: MYR 25000
Delivery location: Kuala Lumpur
Number of users: 15
Specific requirements:
- WiFi coverage for 3 floors
- NAS for shared files
- UPS backup power
- Microsoft 365 for all users
- Video conferencing room setup
"""

    brief = ParserAgent().parse(brief_text)

    assert brief.client_name == "Acme KL Office"
    assert "networking" in brief.inferred_categories
    assert "peripheral" in brief.inferred_categories
    assert brief.num_users == 15
    assert fake_client.completions.calls == 1


def test_reviewer_uses_ai_qa_with_deterministic_baseline(monkeypatch) -> None:
    ai_payload = {
        "approved": True,
        "risk_flags": [],
        "suggestions": ["Confirm stock and warranty terms before procurement."],
        "overall_assessment": "AI reviewer confirms the quote covers requirements, budget, delivery, and compatibility for the office brief.",
        "technical_score": 8.6,
        "commercial_score": 8.3,
    }
    fake_client = _FakeClient(ai_payload)

    monkeypatch.setattr(reviewer_agent, "get_chutes_client", lambda: fake_client)
    monkeypatch.setattr(sales_engineer_agent, "get_chutes_client", lambda: _FakeClient({}))
    solution = SalesEngineerAgent().build_solution(_office_brief())

    feedback = ReviewerAgent().review(_office_brief(), solution)

    assert feedback.approved is True
    assert feedback.technical_score >= 6.5
    assert feedback.commercial_score >= 6.5
    assert fake_client.completions.calls == 1


def test_pipeline_report_includes_hackathon_evidence() -> None:
    brief = _office_brief()
    solution = {
        "selected_products": [
            {"product_id": "prod_net_003", "quantity": 3, "confidence_score": 0.92, "confidence_reason": "Covers WiFi for three floors.", "alternatives_considered": []},
            {"product_id": "prod_net_004", "quantity": 1, "confidence_score": 0.86, "confidence_reason": "Provides switching for office users.", "alternatives_considered": []},
            {"product_id": "prod_sto_005", "quantity": 1, "confidence_score": 0.89, "confidence_reason": "Provides NAS file sharing.", "alternatives_considered": []},
            {"product_id": "prod_sto_002", "quantity": 2, "confidence_score": 0.84, "confidence_reason": "Adds storage drives for redundancy.", "alternatives_considered": []},
            {"product_id": "prod_pwr_002", "quantity": 1, "confidence_score": 0.84, "confidence_reason": "Covers UPS backup power.", "alternatives_considered": []},
            {"product_id": "prod_sft_001", "quantity": 15, "confidence_score": 0.88, "confidence_reason": "Covers Microsoft 365 for all users.", "alternatives_considered": []},
            {"product_id": "prod_per_005", "quantity": 1, "confidence_score": 0.87, "confidence_reason": "Covers video conferencing room setup.", "alternatives_considered": []},
        ],
        "solution_summary": "Catalog-backed office quote.",
        "reasoning_summary": "Selected products cover the client constraints with catalog evidence.",
        "recommendations": [],
        "warnings": [],
        "self_critique_history": [],
    }
    reviewer_feedback = ReviewerFeedback(
        approved=True,
        risk_flags=[],
        suggestions=[],
        overall_assessment="Approved for budgetary quote.",
        technical_score=8.4,
        commercial_score=8.0,
    )
    steps = [
        AgentStep(iteration=1, agent_name="Parser", action="AI-refined structured brief", tool_called=None, tool_args={"model": "fake"}, tool_result_summary="ok", timestamp="2026-05-27T00:00:00Z"),
        AgentStep(iteration=2, agent_name="SalesEngineer", action="Searched catalog for networking", tool_called="search_catalog", tool_args={"category": "networking"}, tool_result_summary="ok", timestamp="2026-05-27T00:00:01Z"),
        AgentStep(iteration=3, agent_name="SalesEngineer", action="AI refined catalog-backed solution plan", tool_called=None, tool_args={"model": "fake"}, tool_result_summary="ok", timestamp="2026-05-27T00:00:02Z"),
        AgentStep(iteration=4, agent_name="Reviewer", action="AI reviewed final solution quality and risk", tool_called=None, tool_args={"model": "fake"}, tool_result_summary="ok", timestamp="2026-05-27T00:00:03Z"),
    ]

    report = SalesEngineerPipeline()._assemble_report(brief, solution, reviewer_feedback, steps, 3.2)

    assert report.handbook_score_pct > 70
    assert report.hackathon_scorecard
    assert report.constraint_decisions
    assert all(item.status == "covered" for item in report.constraint_decisions)
    assert report.supplier_evidence
    assert report.agentic_evidence
    assert "flowchart" in report.architecture_diagram
    assert report.demo_pitch