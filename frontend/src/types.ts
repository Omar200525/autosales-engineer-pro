export type PipelineStatus = "queued" | "running" | "completed" | "failed";
export type TelegramNotificationStatus = "disabled" | "pending" | "sent" | "failed";

export type Product = {
  id: string;
  name: string;
  category: string;
  price_myr: number;
  specs: Record<string, unknown>;
  compatible_with: string[];
  available_regions: string[];
  in_stock: boolean;
  brand: string;
  url: string;
  source_platform: string;
};

export type CatalogStats = {
  total_products: number;
  min_price: number;
  max_price: number;
  categories: Record<string, { count: number; min_price: number; max_price: number }>;
};

export type AgentStep = {
  iteration: number;
  agent_name: "VisualAnalyst" | "Parser" | "SalesEngineer" | "Reviewer";
  action: string;
  tool_called: string | null;
  tool_args: Record<string, unknown> | null;
  tool_result_summary: string;
  timestamp: string;
};

export type QuoteLineItem = {
  product_id: string;
  product_name: string;
  brand: string;
  category: string;
  quantity: number;
  unit_price_myr: number;
  subtotal_myr: number;
  confidence_score: number;
  confidence_reason: string;
  product_url: string;
  source_platform: string;
  shipping_fee_myr: number;
  sst_myr: number;
  tco_myr: number;
};

export type ReviewerFeedback = {
  approved: boolean;
  risk_flags: string[];
  suggestions: string[];
  overall_assessment: string;
  technical_score: number;
  commercial_score: number;
};

export type HackathonCriterion = {
  category: string;
  criterion: string;
  max_points: number;
  score: number;
  evidence: string[];
  improvement_hint: string;
};

export type ConstraintDecision = {
  requirement: string;
  status: "covered" | "partial" | "needs_review";
  evidence: string;
  covered_by: string[];
};

export type SupplierEvidence = {
  product_id: string;
  product_name: string;
  source_platform: string;
  url: string;
  price_myr: number;
  region_status: string;
  confidence_score: number;
};

export type AgenticEvidence = {
  label: string;
  status: "pass" | "warn" | "info";
  evidence: string;
};

export type SolutionReport = {
  client_name: string;
  use_case: string;
  delivery_location: string;
  line_items: QuoteLineItem[];
  total_price_myr: number;
  budget_myr: number;
  within_budget: boolean;
  budget_utilization_pct: number;
  compatibility_matrix: { pairs_checked: Record<string, unknown>[]; all_compatible: boolean; issues: string[] };
  delivery_feasible: boolean;
  unavailable_products: string[];
  self_critique_history: Record<string, unknown>[];
  reviewer_feedback: ReviewerFeedback;
  executive_summary: string;
  recommendations: string[];
  warnings: string[];
  agent_steps: AgentStep[];
  total_iterations: number;
  pipeline_duration_seconds: number;
  brief_source: "text" | "image" | "combined";
  reasoning_summary: string;
  delivery_timeline_estimate: string;
  logistics_tco_total_myr: number;
  handbook_score_pct: number;
  hackathon_scorecard: HackathonCriterion[];
  constraint_decisions: ConstraintDecision[];
  supplier_evidence: SupplierEvidence[];
  agentic_evidence: AgenticEvidence[];
  logistics_assumptions: string[];
  architecture_diagram: string;
  demo_pitch: string[];
  next_best_enhancements: string[];
};

export type PipelineRunCreated = {
  run_id: string;
  status: PipelineStatus;
  events_url: string;
  result_url: string;
};

export type PipelineRunSnapshot = {
  run_id: string;
  status: PipelineStatus;
  steps: AgentStep[];
  report: SolutionReport | null;
  error: string | null;
  created_at: string;
  updated_at: string;
  telegram_status: TelegramNotificationStatus;
  telegram_error: string | null;
  telegram_sent_at: string | null;
};
