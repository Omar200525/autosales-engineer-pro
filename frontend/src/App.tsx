import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  BadgeCheck,
  Boxes,
  BrainCircuit,
  CheckCircle2,
  CircleDashed,
  ClipboardList,
  Clock3,
  Database,
  Download,
  FileCheck2,
  FileText,
  Gauge,
  ImagePlus,
  Layers3,
  Link2,
  Loader2,
  PackageSearch,
  Play,
  Route,
  Search,
  ShieldCheck,
  Sparkles,
  Target,
  Upload,
  WandSparkles,
  XCircle
} from "lucide-react";

import { createPipelineRun, downloadPdf, getCatalogProducts, getCatalogStats, streamPipelineRun } from "./api";
import type { AgentStep, Product, SolutionReport } from "./types";

const DEFAULT_BRIEF = `Client: Acme KL Office
Use case: Small office setup for 15 staff with secure internet, WiFi, file sharing, Microsoft 365, and video conferencing.
Budget: MYR 25000
Delivery location: Kuala Lumpur
Number of users: 15
Specific requirements:
- WiFi coverage for 3 floors
- NAS for shared files
- UPS backup power
- Microsoft 365 for all users
- Video conferencing room setup`;

const TEMPLATES = [
  { label: "Office", detail: "15 users", brief: DEFAULT_BRIEF },
  {
    label: "Server Room",
    detail: "50 users",
    brief: `Client: TechCorp Penang
Use case: SME server room with NAS, compute, networking, and backup power for 50 staff.
Budget: MYR 85000
Delivery location: Penang
Number of users: 50
Specific requirements:
- Rack server with NAS
- Managed switch and firewall
- WiFi 6 access points
- UPS for server room
- Veeam backup solution`
  },
  {
    label: "Studio",
    detail: "Creative team",
    brief: `Client: PixelWorks Studio
Use case: Creative studio setup for 10 designers with high-performance workstations, 4K monitors, and fast storage.
Budget: MYR 38000
Delivery location: Kuala Lumpur
Number of users: 10
Specific requirements:
- High-performance mini PCs
- 4K monitors
- Fast NVMe shared storage
- Wireless keyboards and mice
- Microsoft 365 licenses`
  }
];

const AGENT_DETAILS = [
  { name: "VisualAnalyst", label: "Vision", helper: "Image evidence", icon: ImagePlus },
  { name: "Parser", label: "Parser", helper: "Requirement model", icon: ClipboardList },
  { name: "SalesEngineer", label: "Engineer", helper: "BOM selection", icon: BrainCircuit },
  { name: "Reviewer", label: "Reviewer", helper: "Risk and value", icon: ShieldCheck }
] as const;

const NAV_ITEMS = [
  { id: "brief", label: "Brief", helper: "Input", icon: ClipboardList },
  { id: "pipeline", label: "Pipeline", helper: "Live trace", icon: Activity },
  { id: "report", label: "Report", helper: "Review", icon: FileText },
  { id: "catalog", label: "Catalog", helper: "Products", icon: Boxes }
] as const;

type IconType = typeof Activity;
type NavId = (typeof NAV_ITEMS)[number]["id"];

type RunState = "idle" | "running" | "completed" | "failed";

function money(value: number): string {
  return `MYR ${value.toLocaleString("en-MY", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function percent(value: number): string {
  return `${Math.round(value)}%`;
}

function App() {
  const [brief, setBrief] = useState(DEFAULT_BRIEF);
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [report, setReport] = useState<SolutionReport | null>(null);
  const [runState, setRunState] = useState<RunState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [catalogQuery, setCatalogQuery] = useState("");
  const [category, setCategory] = useState("");
  const [imagePayload, setImagePayload] = useState<{ image_base64: string; image_media_type: string } | null>(null);
  const [activeSection, setActiveSection] = useState<NavId>("brief");
  const activeSectionRef = useRef<NavId>("brief");

  const statsQuery = useQuery({ queryKey: ["catalog-stats"], queryFn: getCatalogStats });
  const categories = useMemo(() => Object.keys(statsQuery.data?.categories ?? {}), [statsQuery.data]);
  const productsQuery = useQuery({
    queryKey: ["catalog-products", category, catalogQuery],
    queryFn: () => getCatalogProducts(category || undefined, catalogQuery || undefined)
  });
  const latestStep = steps[steps.length - 1];
  const selectedTemplate = TEMPLATES.find((template) => template.brief === brief)?.label ?? "Custom";
  const completedAgents = useMemo(() => new Set(steps.map((step) => step.agent_name)).size, [steps]);
  const railStatusLabel = runState === "running"
    ? `${latestStep?.agent_name ?? "Starting"} - ${steps.length} events`
    : report
      ? `${runState} - ${money(report.total_price_myr)}`
      : `${runState} - ${categories.length} categories`;

  useEffect(() => {
    const sections = NAV_ITEMS
      .map((item) => ({ id: item.id, element: document.getElementById(item.id) }))
      .filter((item): item is { id: NavId; element: HTMLElement } => Boolean(item.element));
    if (!sections.length) return;

    let frame = 0;

    const syncActiveSection = () => {
      frame = 0;
      const anchor = Math.min(window.innerHeight * 0.32, 260);
      const ranked = sections
        .map(({ id, element }, index) => {
          const rect = element.getBoundingClientRect();
          const visible = rect.bottom > 0 && rect.top < window.innerHeight;
          const distance = Math.abs(rect.top - anchor) + (rect.top > anchor ? 140 : 0);
          return { id, index, rect, visible, distance };
        })
        .filter((item) => item.visible)
        .sort((first, second) => first.distance - second.distance || first.index - second.index);

      const best = ranked[0];
      if (!best) return;

      const tiedRow = ranked.filter((item) => Math.abs(item.rect.top - best.rect.top) < 8);
      const current = activeSectionRef.current;
      const next = tiedRow.find((item) => item.id === current) ?? best;

      if (next.id !== current) {
        activeSectionRef.current = next.id;
        setActiveSection(next.id);
      }
    };

    const scheduleSync = () => {
      if (frame) return;
      frame = window.requestAnimationFrame(syncActiveSection);
    };

    scheduleSync();
    window.addEventListener("scroll", scheduleSync, { passive: true });
    window.addEventListener("resize", scheduleSync);

    return () => {
      if (frame) window.cancelAnimationFrame(frame);
      window.removeEventListener("scroll", scheduleSync);
      window.removeEventListener("resize", scheduleSync);
    };
  }, []);

  function setActiveNavSection(id: NavId) {
    activeSectionRef.current = id;
    setActiveSection(id);
  }

  async function handleRun() {
    setRunState("running");
    setSteps([]);
    setReport(null);
    setError(null);
    try {
      const run = await createPipelineRun({ raw_brief: brief, ...(imagePayload ?? {}) });
      const source = streamPipelineRun(run.run_id, {
        onStep: (event) => setSteps((current) => [...current, JSON.parse(event.data) as AgentStep]),
        onCompleted: (event) => {
          const completedReport = JSON.parse(event.data) as SolutionReport;
          setReport(completedReport);
          setRunState("completed");
          source.close();
        },
        onFailed: (event) => {
          const payload = JSON.parse(event.data) as { message: string };
          setError(payload.message);
          setRunState("failed");
          source.close();
        },
        onError: () => {
          setError("Lost connection to the pipeline event stream.");
          setRunState("failed");
          source.close();
        }
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not start pipeline run.");
      setRunState("failed");
    }
  }

  async function handleImage(file: File | null) {
    if (!file) {
      setImagePayload(null);
      return;
    }
    const base64 = await toBase64(file);
    setImagePayload({ image_base64: base64, image_media_type: file.type });
  }

  return (
    <main className="app-shell">
      <aside className="rail" aria-label="Application navigation">
        <button
          className="brand-mark"
          type="button"
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
          aria-label="Back to top"
          data-tooltip="Back to top"
        >
          <WandSparkles size={23} />
        </button>
        <nav className="rail-nav">
          {NAV_ITEMS.map(({ id, label, helper, icon: Icon }) => (
            <a
              key={id}
              href={`#${id}`}
              aria-label={label}
              aria-current={activeSection === id ? "page" : undefined}
              data-active={activeSection === id}
              data-tooltip={`${label} - ${helper}`}
              onClick={() => setActiveNavSection(id)}
            >
              <Icon size={20} />
              <span>{label}</span>
              <small>{helper}</small>
            </a>
          ))}
        </nav>
        <div className="rail-status" data-state={runState} aria-label={`Pipeline status: ${railStatusLabel}`} data-tooltip={railStatusLabel}>
          <span className="rail-status-orb" aria-hidden="true" />
          <strong>{runState === "running" ? latestStep?.agent_name ?? "Starting" : runState}</strong>
          <small>{runState === "running" ? `${steps.length} events` : report ? money(report.total_price_myr) : `${categories.length} categories`}</small>
          <div className="rail-progress" aria-hidden="true">
            <span style={{ width: `${Math.max(8, (completedAgents / AGENT_DETAILS.length) * 100)}%` }} />
          </div>
        </div>
        <button
          className="rail-action"
          type="button"
          onClick={handleRun}
          disabled={runState === "running"}
          aria-label="Generate solution"
          data-tooltip={runState === "running" ? "Pipeline running" : "Run pipeline"}
        >
          {runState === "running" ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
          <span>{runState === "running" ? "Running" : "Run"}</span>
        </button>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div className="title-group">
            <p className="eyebrow"><Sparkles size={14} /> AutoSales Engineer Pro</p>
            <h1>AI quote command center</h1>
            <p className="subtitle">From messy client brief to reviewed BOM, delivery check, and exportable quote.</p>
          </div>
          <div className="health-strip" aria-label="System status">
            <StatusPill label="Catalog" value={`${statsQuery.data?.total_products ?? 0} items`} tone="info" icon={Database} />
            <StatusPill label="Mode" value={selectedTemplate} tone="neutral" icon={Layers3} />
            <StatusPill label="Run" value={runState} tone={runTone(runState)} icon={Gauge} />
          </div>
        </header>

        <section className="mission-strip" aria-label="Pipeline value summary">
          <div>
            <span className="mission-icon"><BrainCircuit size={18} /></span>
            <strong>Four-agent pipeline</strong>
            <p>Vision, parser, sales engineer, reviewer.</p>
          </div>
          <div>
            <span className="mission-icon"><PackageSearch size={18} /></span>
            <strong>Catalog-backed</strong>
            <p>Local products, MYR pricing, delivery regions.</p>
          </div>
          <div>
            <span className="mission-icon"><FileCheck2 size={18} /></span>
            <strong>Quote-ready</strong>
            <p>Risk, compatibility, SST, logistics, PDF.</p>
          </div>
        </section>

        <section className="layout-grid">
          <section className="brief-panel surface" id="brief">
            <SectionTitle icon={ClipboardList} label="Brief intake" action="Template assisted" />
            <div className="template-row">
              {TEMPLATES.map((template) => (
                <button key={template.label} type="button" className="template-button" onClick={() => setBrief(template.brief)}>
                  <span>{template.label}</span>
                  <small>{template.detail}</small>
                </button>
              ))}
            </div>
            <textarea value={brief} onChange={(event) => setBrief(event.target.value)} aria-label="Client procurement brief" />
            <div className="brief-actions">
              <label className="upload-target">
                <Upload size={18} />
                <span>{imagePayload ? "Image attached" : "Attach image brief"}</span>
                <input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => handleImage(event.target.files?.[0] ?? null)} />
              </label>
              <button className="primary-button" type="button" onClick={handleRun} disabled={runState === "running"}>
                {runState === "running" ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
                Generate solution
              </button>
            </div>
            {error && <InlineNotice tone="bad" icon={AlertTriangle} text={error} />}
          </section>

          <section className="pipeline-panel surface" id="pipeline">
            <SectionTitle icon={Activity} label="Live pipeline" action={latestStep ? latestStep.agent_name : "Waiting"} />
            <PipelineTracker steps={steps} running={runState === "running"} />
            <div className="current-step">
              <span className="current-step-icon">{runState === "running" ? <Loader2 className="spin" size={18} /> : <Clock3 size={18} />}</span>
              <div>
                <p>{latestStep ? latestStep.action : "Ready to start the agent chain"}</p>
                <small>{latestStep ? latestStep.tool_result_summary : "Pipeline events will stream here as the backend runs."}</small>
              </div>
            </div>
            <div className="step-feed">
              {steps.length === 0 ? (
                <EmptyState icon={CircleDashed} title="No agent events yet" detail="Start a run to watch tool calls, fallbacks, and reviewer checks." />
              ) : (
                steps.slice(-12).reverse().map((step, index) => <StepItem key={`${step.timestamp}-${index}`} step={step} />)
              )}
            </div>
          </section>
        </section>

        <ReportPanel report={report} />
        <CatalogPanel
          products={productsQuery.data?.products ?? []}
          categories={categories}
          category={category}
          catalogQuery={catalogQuery}
          onCategoryChange={setCategory}
          onQueryChange={setCatalogQuery}
        />
      </section>
    </main>
  );
}

function SectionTitle({ icon: Icon, label, action }: { icon: IconType; label: string; action?: string }) {
  return (
    <div className="section-title">
      <div>
        <Icon size={18} />
        <h2>{label}</h2>
      </div>
      {action && <span>{action}</span>}
    </div>
  );
}

function StatusPill({ label, value, tone, icon: Icon }: { label: string; value: string; tone: "neutral" | "info" | "good" | "bad" | "warn"; icon: IconType }) {
  return (
    <span className="status-pill" data-tone={tone}>
      <Icon size={15} />
      <b>{label}</b>
      {value}
    </span>
  );
}

function PipelineTracker({ steps, running }: { steps: AgentStep[]; running: boolean }) {
  const seen = new Set(steps.map((step) => step.agent_name));
  const latest = steps[steps.length - 1]?.agent_name;
  return (
    <div className="tracker" aria-label="Pipeline progress">
      {AGENT_DETAILS.map(({ name, label, helper, icon: Icon }) => {
        const done = seen.has(name);
        const active = running && latest === name;
        return (
          <div className="tracker-node" data-state={active ? "active" : done ? "done" : "idle"} key={name}>
            <span>{done ? <CheckCircle2 size={16} /> : <Icon size={16} />}</span>
            <strong>{label}</strong>
            <p>{helper}</p>
          </div>
        );
      })}
    </div>
  );
}

function StepItem({ step }: { step: AgentStep }) {
  return (
    <article className="step-item">
      <span className={`agent-dot agent-${step.agent_name.toLowerCase()}`} aria-hidden="true" />
      <div>
        <p className="step-meta">{step.agent_name} · {step.timestamp.slice(11, 19)}</p>
        <h3>{step.action}</h3>
        <p>{step.tool_result_summary}</p>
      </div>
    </article>
  );
}

function ReportPanel({ report }: { report: SolutionReport | null }) {
  return (
    <section className="report-panel" id="report">
      <SectionTitle icon={FileText} label="Solution report" action={report ? report.client_name : "Awaiting run"} />
      {!report ? (
        <EmptyState icon={FileText} title="No quote generated" detail="Run the agent pipeline to review totals, risks, logistics, and export options." />
      ) : (
        <>
          <div className="report-hero surface-emphasis">
            <div>
              <p className="eyebrow"><BadgeCheck size={14} /> Reviewed proposal</p>
              <h2>{report.client_name}</h2>
              <p>{report.executive_summary}</p>
            </div>
            <div className="report-actions">
              <StatusPill label="Budget" value={report.within_budget ? "within" : "over"} tone={report.within_budget ? "good" : "bad"} icon={report.within_budget ? CheckCircle2 : XCircle} />
              <StatusPill label="Delivery" value={report.delivery_feasible ? "feasible" : "review"} tone={report.delivery_feasible ? "good" : "warn"} icon={report.delivery_feasible ? CheckCircle2 : AlertTriangle} />
              <button className="secondary-button" type="button" onClick={() => downloadPdf(report)}>
                <Download size={18} />
                Download PDF
              </button>
            </div>
          </div>

          <div className="metric-row">
            <Metric label="Total quote" value={money(report.total_price_myr)} tone={report.within_budget ? "good" : "bad"} />
            <Metric label="Budget use" value={`${report.budget_utilization_pct.toFixed(1)}%`} />
            <Metric label="Technical" value={`${report.reviewer_feedback.technical_score.toFixed(1)}/10`} />
            <Metric label="Commercial" value={`${report.reviewer_feedback.commercial_score.toFixed(1)}/10`} />
            <Metric label="TCO" value={money(report.logistics_tco_total_myr)} />
          </div>

          <EvidenceMatrix report={report} />

          <div className="report-grid">
            <div className="table-wrap bom-table">
              <table>
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Brand</th>
                    <th>Qty</th>
                    <th>Subtotal</th>
                    <th>TCO</th>
                  </tr>
                </thead>
                <tbody>
                  {report.line_items.map((item) => (
                    <tr key={item.product_id}>
                      <td><a href={item.product_url} target="_blank" rel="noreferrer">{item.product_name}</a></td>
                      <td>{item.brand}</td>
                      <td>{item.quantity}</td>
                      <td>{money(item.subtotal_myr)}</td>
                      <td>{money(item.tco_myr)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <aside className="review-panel surface">
              <h3>Reviewer signal</h3>
              <p>{report.reviewer_feedback.overall_assessment}</p>
              <div className="risk-stack">
                {(report.warnings.length ? report.warnings : ["No major warnings reported."]).slice(0, 4).map((warning) => (
                  <InlineNotice key={warning} tone="warn" icon={AlertTriangle} text={warning} />
                ))}
              </div>
            </aside>
          </div>
        </>
      )}
    </section>
  );
}

function EvidenceMatrix({ report }: { report: SolutionReport }) {
  const constraints = (report.constraint_decisions ?? []).slice(0, 7);
  const supplierEvidence = (report.supplier_evidence ?? []).slice(0, 6);
  const agenticEvidence = report.agentic_evidence ?? [];
  return (
    <section className="evidence-matrix" aria-label="Quote evidence">
      <div className="evidence-block">
        <div className="evidence-heading"><Route size={17} /><h3>Constraint proof</h3></div>
        <div className="decision-list">
          {constraints.map((decision) => (
            <article className="decision-row" data-status={decision.status} key={decision.requirement}>
              <span>{decision.status === "covered" ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}</span>
              <div>
                <strong>{decision.requirement}</strong>
                <p>{decision.evidence}</p>
              </div>
            </article>
          ))}
        </div>
      </div>

      <div className="evidence-block">
        <div className="evidence-heading"><Link2 size={17} /><h3>Supplier evidence</h3></div>
        <div className="supplier-list">
          {supplierEvidence.map((item) => (
            <a className="supplier-row" href={item.url} target="_blank" rel="noreferrer" key={item.product_id}>
              <span><Link2 size={14} /></span>
              <div>
                <strong>{item.product_name}</strong>
                <p>{item.source_platform} · {money(item.price_myr)} · {percent(item.confidence_score * 100)} confidence</p>
              </div>
            </a>
          ))}
        </div>
      </div>

      <div className="evidence-block">
        <div className="evidence-heading"><Target size={17} /><h3>Agentic proof</h3></div>
        <div className="agentic-list">
          {agenticEvidence.map((item) => (
            <article className="agentic-row" data-status={item.status} key={item.label}>
              <span>{item.status}</span>
              <div>
                <strong>{item.label}</strong>
                <p>{item.evidence}</p>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

function Metric({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "neutral" | "good" | "bad" }) {
  return (
    <div className="metric" data-tone={tone}>
      <p>{label}</p>
      <strong>{value}</strong>
    </div>
  );
}

function CatalogPanel({
  products,
  categories,
  category,
  catalogQuery,
  onCategoryChange,
  onQueryChange
}: {
  products: Product[];
  categories: string[];
  category: string;
  catalogQuery: string;
  onCategoryChange: (value: string) => void;
  onQueryChange: (value: string) => void;
}) {
  return (
    <section className="catalog-panel" id="catalog">
      <SectionTitle icon={Boxes} label="Catalog intelligence" action={`${products.length} visible`} />
      <div className="filter-row">
        <label>
          <Search size={16} />
          <input value={catalogQuery} onChange={(event) => onQueryChange(event.target.value)} placeholder="Search brand, product, category" />
        </label>
        <select value={category} onChange={(event) => onCategoryChange(event.target.value)} aria-label="Catalog category">
          <option value="">All categories</option>
          {categories.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
      </div>
      <div className="category-chips" aria-label="Catalog categories">
        <button type="button" data-active={!category} onClick={() => onCategoryChange("")}>All</button>
        {categories.map((item) => (
          <button type="button" key={item} data-active={category === item} onClick={() => onCategoryChange(item)}>{item}</button>
        ))}
      </div>
      <div className="table-wrap compact">
        <table>
          <thead>
            <tr>
              <th>Product</th>
              <th>Category</th>
              <th>Regions</th>
              <th>Price</th>
            </tr>
          </thead>
          <tbody>
            {products.slice(0, 14).map((product) => (
              <tr key={product.id}>
                <td>{product.name}</td>
                <td>{product.category}</td>
                <td>{product.available_regions.join(", ")}</td>
                <td>{money(product.price_myr)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function EmptyState({ icon: Icon, title, detail }: { icon: IconType; title: string; detail: string }) {
  return (
    <div className="empty-state">
      <Icon size={26} />
      <strong>{title}</strong>
      <p>{detail}</p>
    </div>
  );
}

function InlineNotice({ tone, icon: Icon, text }: { tone: "bad" | "warn" | "good"; icon: IconType; text: string }) {
  return (
    <p className="inline-notice" data-tone={tone}>
      <Icon size={16} />
      <span>{text}</span>
    </p>
  );
}

function runTone(runState: RunState): "neutral" | "info" | "good" | "bad" | "warn" {
  if (runState === "completed") return "good";
  if (runState === "failed") return "bad";
  if (runState === "running") return "info";
  return "neutral";
}

function toBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const value = String(reader.result ?? "");
      resolve(value.includes(",") ? value.split(",")[1] : value);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

export default App;
