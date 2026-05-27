"""Pydantic v2 models used throughout the sales engineering pipeline."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Category = Literal[
    "networking",
    "compute",
    "storage",
    "display",
    "peripheral",
    "software_license",
    "power",
    "cooling",
]


class Product(BaseModel):
    """A catalog or externally discovered product."""

    id: str
    name: str
    category: Category
    price_myr: float
    specs: dict[str, Any]
    compatible_with: list[str]
    available_regions: list[str]
    in_stock: bool
    brand: str
    url: str = ""
    source_platform: str = "catalog"


class VisualExtraction(BaseModel):
    """Structured information extracted from an uploaded image."""

    raw_text_extracted: str
    client_name: Optional[str]
    detected_requirements: list[str]
    detected_budget_myr: Optional[float]
    detected_location: Optional[str]
    detected_num_users: Optional[int]
    confidence: float = Field(ge=0.0, le=1.0)
    image_type: Literal["whiteboard", "document", "diagram", "photo", "unknown"]


class StructuredBrief(BaseModel):
    """Normalized client requirements."""

    client_name: str
    use_case: str
    budget_myr: float
    delivery_location: str
    num_users: Optional[int]
    requirements: list[str]
    inferred_categories: list[Category]
    priority: Literal["budget", "performance", "balanced"]
    source: Literal["text", "image", "combined"]


class ProductRecommendation(BaseModel):
    """A selected product with confidence metadata."""

    product: Product
    quantity: int
    confidence_score: float = Field(ge=0.0, le=1.0)
    confidence_reason: str
    alternatives_considered: list[str]


class QuoteLineItem(BaseModel):
    """A bill-of-materials line item."""

    product_id: str
    product_name: str
    brand: str
    category: str
    quantity: int
    unit_price_myr: float
    subtotal_myr: float
    confidence_score: float = Field(ge=0.0, le=1.0)
    confidence_reason: str
    product_url: str
    source_platform: str
    shipping_fee_myr: float
    sst_myr: float
    tco_myr: float


class CompatibilityMatrix(BaseModel):
    """Compatibility checks between selected products."""

    pairs_checked: list[dict]
    all_compatible: bool
    issues: list[str]


class SelfCritiqueResult(BaseModel):
    """Result of one self-critique pass."""

    passed: bool
    iteration: int
    issues_found: list[str]
    improvements_made: list[str]
    budget_status: Literal["within", "over", "under_by_large_margin"]
    compatibility_status: str


class ReviewerFeedback(BaseModel):
    """Final reviewer assessment."""

    approved: bool
    risk_flags: list[str]
    suggestions: list[str]
    overall_assessment: str
    technical_score: float = Field(ge=0.0, le=10.0)
    commercial_score: float = Field(ge=0.0, le=10.0)


class HackathonCriterion(BaseModel):
    """Guide-book scoring evidence for judges."""

    category: str
    criterion: str
    max_points: float
    score: float
    evidence: list[str]
    improvement_hint: str


class ConstraintDecision(BaseModel):
    """How a client requirement was covered or flagged."""

    requirement: str
    status: Literal["covered", "partial", "needs_review"]
    evidence: str
    covered_by: list[str]


class SupplierEvidence(BaseModel):
    """Catalog or external supplier evidence for one selected line."""

    product_id: str
    product_name: str
    source_platform: str
    url: str
    price_myr: float
    region_status: str
    confidence_score: float = Field(ge=0.0, le=1.0)


class AgenticEvidence(BaseModel):
    """Visible proof of agentic AI, tools, and guardrails."""

    label: str
    status: Literal["pass", "warn", "info"]
    evidence: str


class AgentStep(BaseModel):
    """A trace entry emitted by an agent."""

    iteration: int
    agent_name: Literal["VisualAnalyst", "Parser", "SalesEngineer", "Reviewer"]
    action: str
    tool_called: Optional[str]
    tool_args: Optional[dict]
    tool_result_summary: str
    timestamp: str


class SolutionReport(BaseModel):
    """Complete proposal returned by the pipeline."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    client_name: str
    use_case: str
    delivery_location: str
    line_items: list[QuoteLineItem]
    total_price_myr: float
    budget_myr: float
    within_budget: bool
    budget_utilization_pct: float
    compatibility_matrix: CompatibilityMatrix
    delivery_feasible: bool
    unavailable_products: list[str]
    self_critique_history: list[SelfCritiqueResult]
    reviewer_feedback: ReviewerFeedback
    executive_summary: str
    recommendations: list[str]
    warnings: list[str]
    agent_steps: list[AgentStep]
    total_iterations: int
    pipeline_duration_seconds: float
    brief_source: Literal["text", "image", "combined"]
    reasoning_summary: str
    delivery_timeline_estimate: str
    logistics_tco_total_myr: float
    handbook_score_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    hackathon_scorecard: list[HackathonCriterion] = Field(default_factory=list)
    constraint_decisions: list[ConstraintDecision] = Field(default_factory=list)
    supplier_evidence: list[SupplierEvidence] = Field(default_factory=list)
    agentic_evidence: list[AgenticEvidence] = Field(default_factory=list)
    logistics_assumptions: list[str] = Field(default_factory=list)
    architecture_diagram: str = ""
    demo_pitch: list[str] = Field(default_factory=list)
    next_best_enhancements: list[str] = Field(default_factory=list)


class ToolResult(BaseModel):
    """Standard result shape returned by all tools."""

    success: bool
    data: Any
    error: Optional[str] = None
