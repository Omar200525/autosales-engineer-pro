"""Production Streamlit UI for AutoSales Engineer Pro."""

from __future__ import annotations

import time
from html import escape

import pandas as pd
import streamlit as st

from core import catalog
from core.catalog import get_all_categories, get_catalog_stats, search_products
from core.models import AgentStep
from core.pdf_generator import generate_pdf
from core.tools import calculate_budget_fit
from pipeline import SalesEngineerPipeline


st.set_page_config(
    page_title="AutoSales Engineer Pro",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def inject_css() -> None:
    """Inject the complete visual system."""
    st.markdown(
        """
<style>
[data-testid="stAppViewContainer"],
[data-theme="dark"],
html[data-theme="dark"],
body[data-theme="dark"],
:root {
  --bg-base: #0a0f1e;
  --bg-surface: #111827;
  --bg-elevated: #1a2235;
  --border: rgba(255,255,255,0.08);
  --border-focus: rgba(99,102,241,0.6);
  --text-primary: #f1f5f9;
  --text-secondary: #94a3b8;
  --text-muted: #475569;
  --accent: #6366f1;
  --accent-glow: rgba(99,102,241,0.25);
  --green: #10b981;
  --red: #ef4444;
  --amber: #f59e0b;
  --cyan: #06b6d4;
}
[data-theme="light"],
html[data-theme="light"],
body[data-theme="light"],
.stApp[data-theme="light"] {
  --bg-base: #f8fafc;
  --bg-surface: #ffffff;
  --bg-elevated: #f1f5f9;
  --border: rgba(0,0,0,0.08);
  --border-focus: rgba(99,102,241,0.5);
  --text-primary: #0f172a;
  --text-secondary: #475569;
  --text-muted: #94a3b8;
  --accent: #6366f1;
  --accent-glow: rgba(99,102,241,0.15);
  --green: #059669;
  --red: #dc2626;
  --amber: #d97706;
  --cyan: #0891b2;
}
@media (prefers-color-scheme: light) {
  :root {
    --bg-base: #f8fafc;
    --bg-surface: #ffffff;
    --bg-elevated: #f1f5f9;
    --border: rgba(0,0,0,0.08);
    --border-focus: rgba(99,102,241,0.5);
    --text-primary: #0f172a;
    --text-secondary: #475569;
    --text-muted: #94a3b8;
    --accent: #6366f1;
    --accent-glow: rgba(99,102,241,0.15);
    --green: #059669;
    --red: #dc2626;
    --amber: #d97706;
    --cyan: #0891b2;
  }
}
[data-theme="dark"],
html[data-theme="dark"],
body[data-theme="dark"],
.stApp[data-theme="dark"] {
  --bg-base: #0a0f1e;
  --bg-surface: #111827;
  --bg-elevated: #1a2235;
  --border: rgba(255,255,255,0.08);
  --border-focus: rgba(99,102,241,0.6);
  --text-primary: #f1f5f9;
  --text-secondary: #94a3b8;
  --text-muted: #475569;
  --accent: #6366f1;
  --accent-glow: rgba(99,102,241,0.25);
  --green: #10b981;
  --red: #ef4444;
  --amber: #f59e0b;
  --cyan: #06b6d4;
}
html, body, [data-testid="stAppViewContainer"] {
  background: var(--bg-base) !important;
  color: var(--text-primary) !important;
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif !important;
}
* {
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif !important;
}
[data-testid="stIconMaterial"],
.material-symbols-rounded,
.material-symbols-outlined,
.material-icons {
  font-family: "Material Symbols Rounded", "Material Symbols Outlined", "Material Icons" !important;
  font-weight: normal !important;
  font-style: normal !important;
  line-height: 1 !important;
  letter-spacing: normal !important;
  text-transform: none !important;
  white-space: nowrap !important;
  word-wrap: normal !important;
  direction: ltr !important;
  font-feature-settings: "liga" !important;
  -webkit-font-feature-settings: "liga" !important;
  -webkit-font-smoothing: antialiased !important;
}
h1, h2, h3, h4, h5, h6 {
  color: var(--text-primary) !important;
  font-weight: 800 !important;
  letter-spacing: -0.02em !important;
}
p, label, span, div, [data-testid="stMarkdownContainer"] {
  letter-spacing: 0;
  color: inherit;
}
[data-testid="stHeader"] {
  background: transparent !important;
}
.block-container {
  padding: 1.5rem 2rem 3rem !important;
  max-width: 1440px !important;
}
[data-testid="stSidebar"] {
  background: var(--bg-surface) !important;
  border-right: 1px solid var(--border) !important;
}
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  background: rgba(99,102,241,0.4);
  border-radius: 3px;
}
.page-header {
  padding: 24px 0 20px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.page-title {
  font-size: 22px;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: -0.02em;
  display: flex;
  align-items: center;
  gap: 10px;
}
.page-subtitle {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 3px;
}
.theme-badge {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid var(--border);
  color: var(--text-muted);
  white-space: nowrap;
}
.bento-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 20px 24px;
  transition: border-color 0.2s, transform 0.2s, box-shadow 0.2s;
  height: 100%;
}
.bento-card:hover {
  border-color: var(--accent);
  transform: translateY(-2px);
  box-shadow: 0 8px 32px var(--accent-glow);
}
.bento-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  margin-bottom: 10px;
}
.bento-value {
  font-size: 28px;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: -0.02em;
  line-height: 1;
}
.bento-sub {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 6px;
}
.bento-accent { color: var(--accent); }
.bento-green  { color: var(--green); }
.bento-red    { color: var(--red); }
.bento-amber  { color: var(--amber); }
.badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 12px;
  font-weight: 700;
  border: 1px solid transparent;
}
.badge-pass {
  background: rgba(16,185,129,0.12);
  color: var(--green);
  border-color: rgba(16,185,129,0.28);
}
.badge-fail {
  background: rgba(239,68,68,0.12);
  color: var(--red);
  border-color: rgba(239,68,68,0.28);
}
.badge-pending {
  background: rgba(245,158,11,0.12);
  color: var(--amber);
  border-color: rgba(245,158,11,0.28);
}
.badge-info {
  background: rgba(99,102,241,0.12);
  color: var(--accent);
  border-color: rgba(99,102,241,0.28);
}
.step-feed {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 420px;
  overflow-y: auto;
  padding-right: 4px;
}
.step-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--bg-surface);
  font-size: 13px;
  line-height: 1.4;
}
.step-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 4px;
  flex-shrink: 0;
}
.dot-visual   { background: #8b5cf6; }
.dot-parser   { background: var(--cyan); }
.dot-engineer { background: var(--green); }
.dot-reviewer { background: var(--amber); }
.step-agent {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
}
.step-action {
  color: var(--text-primary);
  font-weight: 500;
}
.step-result {
  color: var(--text-secondary);
  font-size: 12px;
  margin-top: 2px;
}
.pipeline-track {
  display: flex;
  align-items: center;
  gap: 0;
  padding: 16px 0;
}
.pipe-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
  position: relative;
}
.pipe-node:not(:last-child)::after {
  content: "";
  position: absolute;
  top: 14px;
  left: 55%;
  right: -45%;
  height: 1px;
  background: var(--border);
}
.pipe-node.done::after { background: var(--green); }
.pipe-icon {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 2px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  z-index: 1;
}
.pipe-icon.done {
  background: var(--green);
  border-color: var(--green);
  color: #ffffff;
}
.pipe-icon.active {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-glow);
  animation: pulse-ring 1.4s infinite;
}
@keyframes pulse-ring {
  0%   { box-shadow: 0 0 0 0 var(--accent-glow); }
  70%  { box-shadow: 0 0 0 8px rgba(99,102,241,0); }
  100% { box-shadow: 0 0 0 0 rgba(99,102,241,0); }
}
.pipe-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
  margin-top: 6px;
  text-align: center;
}
.pipe-model {
  font-size: 9px;
  color: var(--text-muted);
  text-align: center;
  margin-top: 2px;
  max-width: 80px;
}
.section-header {
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
  margin: 8px 0 16px;
}
.glass-panel {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 16px 20px;
  margin-bottom: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
}
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stNumberInput"] input {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border) !important;
  border-radius: 10px !important;
  color: var(--text-primary) !important;
  font-size: 14px !important;
  transition: border-color 0.2s !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus,
[data-testid="stNumberInput"] input:focus {
  border-color: var(--border-focus) !important;
  box-shadow: 0 0 0 3px var(--accent-glow) !important;
}
[data-baseweb="select"] {
  background: var(--bg-elevated) !important;
  border-color: var(--border) !important;
  border-radius: 10px !important;
}
.stButton > button {
  background: linear-gradient(135deg, #6366f1, #4f46e5) !important;
  border: none !important;
  border-radius: 10px !important;
  color: #ffffff !important;
  font-weight: 700 !important;
  font-size: 14px !important;
  padding: 10px 20px !important;
  box-shadow: 0 4px 14px rgba(99,102,241,0.35) !important;
  transition: all 0.2s !important;
}
.stButton > button:hover {
  transform: translateY(-1px) !important;
  box-shadow: 0 8px 24px rgba(99,102,241,0.45) !important;
}
.stButton > button[kind="secondary"] {
  background: transparent !important;
  border: 1px solid var(--border) !important;
  color: var(--text-secondary) !important;
  box-shadow: none !important;
}
.stDownloadButton > button {
  background: transparent !important;
  border: 1px solid var(--border) !important;
  color: var(--text-secondary) !important;
  border-radius: 10px !important;
  font-weight: 700 !important;
  box-shadow: none !important;
}
.stDownloadButton > button:hover {
  border-color: var(--accent) !important;
  color: var(--accent) !important;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
  font-weight: 600 !important;
  font-size: 13px !important;
}
[data-testid="stDataFrame"] {
  border-radius: 12px !important;
  overflow: hidden !important;
  border: 1px solid var(--border) !important;
}
[data-testid="stMetric"] {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 14px 16px;
}
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }
@media (max-width: 760px) {
  .block-container { padding: 1rem 1rem 2rem !important; }
  .page-header { align-items: flex-start; flex-direction: column; }
  .bento-value { font-size: 24px; }
  .pipeline-track { overflow-x: auto; }
  .pipe-node { min-width: 96px; }
}
</style>
        """,
        unsafe_allow_html=True,
    )


def is_dark_mode() -> bool:
    """Return the default Python-side theme assumption."""
    return True


def money(value: float) -> str:
    return f"MYR {value:,.2f}"


def pct(value: float) -> str:
    return f"{value:.1f}%"


def short(text: str, length: int = 100) -> str:
    text = str(text or "")
    return text if len(text) <= length else text[: length - 1] + "…"


def badge(text: str, kind: str = "info") -> str:
    """Return an HTML badge string. kind: pass|fail|pending|info."""
    return f'<span class="badge badge-{kind}">{escape(text)}</span>'


def bento_card_html(label: str, value: str, sub: str = "", color_class: str = "") -> str:
    sub_html = f"<div class='bento-sub'>{escape(sub)}</div>" if sub else ""
    return f"""
    <div class="bento-card">
      <div class="bento-label">{escape(label)}</div>
      <div class="bento-value {color_class}">{escape(value)}</div>
      {sub_html}
    </div>
    """


def section_header(text: str) -> None:
    st.markdown(f'<div class="section-header">{escape(text)}</div>', unsafe_allow_html=True)


def pipeline_tracker_html(steps: list[AgentStep], running: bool) -> str:
    """Build the 4-node pipeline tracker HTML."""
    agents = [
        ("VisualAnalyst", "🟣", "Gemini 3.5"),
        ("Parser", "🔵", "Groq Llama"),
        ("SalesEngineer", "🟢", "Qwen 2.5 72B"),
        ("Reviewer", "🟠", "DeepSeek-R1"),
    ]
    step_agents = [s.agent_name for s in steps]
    last_agent = step_agents[-1] if step_agents else None
    nodes_html = ""
    for agent_name, icon, model in agents:
        done = agent_name in step_agents
        active = agent_name == last_agent and running
        icon_class = "done" if done else ("active" if active else "")
        icon_symbol = "✓" if done else ("●" if active else icon)
        connector_class = "done" if done else ""
        nodes_html += (
            f'<div class="pipe-node {connector_class}">'
            f'<div class="pipe-icon {icon_class}">{icon_symbol}</div>'
            f'<div class="pipe-label">{escape(agent_name)}</div>'
            f'<div class="pipe-model">{escape(model)}</div>'
            "</div>"
        )
    return f'<div class="pipeline-track">{nodes_html}</div>'


def render_page_header() -> None:
    st.markdown(
        """
<div class="page-header">
  <div>
    <div class="page-title">⚡ AutoSales Engineer Pro</div>
    <div class="page-subtitle">Four-Agent AI Pipeline · Track 1 · APU AI Marathon 2026</div>
  </div>
  <div class="theme-badge">v1.0 · LLM Everywhere</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            """
<div style="padding:8px 0 16px">
  <div style="font-size:18px;font-weight:800;color:var(--text-primary);letter-spacing:-0.02em">
    ⚡ AutoSales Pro
  </div>
  <div style="font-size:11px;color:var(--accent);font-weight:700;text-transform:uppercase;letter-spacing:0.08em;margin-top:2px">
    AI Sales Engineer
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )
        st.divider()
        st.markdown('<div class="section-header">Agent Pipeline</div>', unsafe_allow_html=True)
        rows = [
            ("#8b5cf6", "Visual Analyst", "Gemini 3.5 Flash"),
            ("#06b6d4", "Parser", "Groq Llama 3.3 70B"),
            ("#10b981", "Sales Engineer", "Qwen 2.5 72B"),
            ("#f59e0b", "Reviewer", "DeepSeek-R1"),
        ]
        for color, agent, model in rows:
            st.markdown(
                f"""
<div style="display:flex;gap:8px;align-items:center;margin:8px 0;color:var(--text-secondary);font-size:13px">
  <span style="width:8px;height:8px;border-radius:50%;background:{color};display:inline-block"></span>
  <span><b style="color:var(--text-primary)">{escape(agent)}</b> — {escape(model)}</span>
</div>
                """,
                unsafe_allow_html=True,
            )
        st.divider()
        stats = get_catalog_stats()
        st.metric("Products", stats["total_products"])
        st.metric("Categories", len(stats["categories"]))
        st.metric("Price Range", f"{money(stats['min_price'])} - {money(stats['max_price'])}")
        st.divider()
        st.caption("© 2026 AutoSales Engineer Pro")


def apply_template_defaults() -> None:
    mapping = {
        "tpl_name": "client_name",
        "tpl_use_case": "use_case",
        "tpl_budget": "budget_myr",
        "tpl_users": "num_users",
        "tpl_location": "delivery_location",
        "tpl_reqs": "requirements",
    }
    for source, target in mapping.items():
        if source in st.session_state:
            st.session_state[target] = st.session_state[source]
            del st.session_state[source]


def reset_state() -> None:
    st.session_state.report = None
    st.session_state.agent_steps = []
    st.session_state.pipeline_running = False
    st.session_state.pipeline_error = None


def render_step_feed() -> None:
    steps = st.session_state.agent_steps
    if not steps and not st.session_state.pipeline_running:
        st.markdown(
            """
<div style="text-align:center;padding:48px 24px;color:var(--text-muted);">
  <div style="font-size:32px;margin-bottom:12px">⚡</div>
  <div style="font-weight:700;font-size:14px;color:var(--text-secondary)">Ready to generate</div>
  <div style="font-size:13px;margin-top:4px">Fill in the brief and click Generate Solution</div>
</div>
            """,
            unsafe_allow_html=True,
        )
        return

    dot_map = {
        "VisualAnalyst": "dot-visual",
        "Parser": "dot-parser",
        "SalesEngineer": "dot-engineer",
        "Reviewer": "dot-reviewer",
    }
    rows = []
    for step in reversed(steps[-20:]):
        dot = dot_map.get(step.agent_name, "dot-parser")
        time_part = step.timestamp[11:19] if step.timestamp and len(step.timestamp) >= 19 else ""
        rows.append(
            f"""
<div class="step-item">
  <div class="step-dot {dot}"></div>
  <div>
    <div class="step-agent">{escape(step.agent_name)} · {escape(time_part)}</div>
    <div class="step-action">{escape(short(step.action, 80))}</div>
    <div class="step-result">{escape(short(step.tool_result_summary, 100))}</div>
  </div>
</div>
            """
        )
    st.markdown(f'<div class="step-feed">{"".join(rows)}</div>', unsafe_allow_html=True)


def render_completion_card() -> None:
    report = st.session_state.report
    if st.session_state.pipeline_running or report is None:
        return
    status_text = "Within Budget" if report.within_budget else "Over Budget"
    status_kind = "pass" if report.within_budget else "fail"
    st.markdown(
        f"""
<div class="bento-card">
  <div class="bento-label">Complete</div>
  <div class="bento-value bento-green">Solution generated in {report.pipeline_duration_seconds:.1f}s</div>
  <div class="bento-sub">Total: {money(report.total_price_myr)}</div>
  <div style="margin-top:10px">{badge(status_text, status_kind)}</div>
  <div class="bento-sub">View full results in Solution Report →</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_new_brief_tab() -> None:
    apply_template_defaults()
    col_form, col_live = st.columns([1, 1], gap="large")

    with col_form:
        section_header("Client Requirements")
        mode = st.radio(
            "Input mode",
            ["📝 Text", "🖼️ Image", "📝 + 🖼️ Both"],
            horizontal=True,
            label_visibility="collapsed",
        )
        uses_text = mode in {"📝 Text", "📝 + 🖼️ Both"}
        uses_image = mode in {"🖼️ Image", "📝 + 🖼️ Both"}

        if "client_name" not in st.session_state:
            st.session_state.client_name = ""
        if "use_case" not in st.session_state:
            st.session_state.use_case = ""
        if "budget_myr" not in st.session_state:
            st.session_state.budget_myr = 25000
        if "num_users" not in st.session_state:
            st.session_state.num_users = 15
        if "delivery_location" not in st.session_state:
            st.session_state.delivery_location = "Kuala Lumpur"
        if "requirements" not in st.session_state:
            st.session_state.requirements = ""

        uploaded_image = None
        if uses_text:
            client_name = st.text_input("Client name", placeholder="e.g. Acme KL Services", key="client_name")
            use_case = st.text_area(
                "Project description",
                placeholder="e.g. New office for 20 staff — WiFi, file sharing, Microsoft 365, video conferencing",
                height=90,
                key="use_case",
            )
            c1, c2 = st.columns(2)
            with c1:
                budget_myr = st.number_input(
                    "Budget (MYR)",
                    min_value=1000,
                    max_value=1000000,
                    step=1000,
                    key="budget_myr",
                )
            with c2:
                num_users = st.number_input(
                    "Users",
                    min_value=1,
                    max_value=5000,
                    key="num_users",
                )
            delivery_location = st.selectbox(
                "Delivery location",
                ["Kuala Lumpur", "Penang", "Johor Bahru", "Kota Kinabalu", "Kuching", "Nationwide"],
                key="delivery_location",
            )
            requirements = st.text_area(
                "Specific requirements (one per line)",
                placeholder="WiFi coverage for 3 floors\nNAS for file sharing\nUPS backup power\nMicrosoft 365 for all users",
                height=110,
                key="requirements",
            )
        else:
            client_name = st.session_state.client_name or "Image Brief Client"
            use_case = st.session_state.use_case or "Image-based procurement brief"
            budget_myr = st.session_state.budget_myr
            num_users = st.session_state.num_users
            delivery_location = st.session_state.delivery_location
            requirements = st.session_state.requirements

        if uses_image:
            uploaded_image = st.file_uploader(
                "Upload brief image",
                type=["jpg", "jpeg", "png", "webp"],
                help="Whiteboard, scanned RFQ, network diagram, or server room photo",
            )
            if uploaded_image:
                st.image(uploaded_image, width="stretch")
                st.caption("🟣 Gemini 3.5 Flash will analyze this image")

        with st.expander("⚡ Quick templates"):
            t1, t2, t3 = st.columns(3)
            with t1:
                if st.button("🏢 Small Office", width="stretch"):
                    st.session_state["tpl_name"] = "Acme KL Office"
                    st.session_state["tpl_use_case"] = "Small office setup for 15 staff with secure internet, WiFi, file sharing, Microsoft 365, and video conferencing."
                    st.session_state["tpl_budget"] = 25000
                    st.session_state["tpl_users"] = 15
                    st.session_state["tpl_location"] = "Kuala Lumpur"
                    st.session_state["tpl_reqs"] = "WiFi coverage for 3 floors\nNAS for shared files\nUPS backup power\nMicrosoft 365 for all users\nVideo conferencing room setup"
                    st.rerun()
            with t2:
                if st.button("🏭 SME Server Room", width="stretch"):
                    st.session_state["tpl_name"] = "TechCorp Penang"
                    st.session_state["tpl_use_case"] = "SME server room with NAS, compute, networking, and backup power for 50 staff."
                    st.session_state["tpl_budget"] = 85000
                    st.session_state["tpl_users"] = 50
                    st.session_state["tpl_location"] = "Penang"
                    st.session_state["tpl_reqs"] = "Rack server with NAS\nManaged switch and firewall\nWiFi 6 access points\nUPS for server room\nVeeam backup solution"
                    st.rerun()
            with t3:
                if st.button("💻 Creative Studio", width="stretch"):
                    st.session_state["tpl_name"] = "PixelWorks Studio"
                    st.session_state["tpl_use_case"] = "Creative studio setup for 10 designers with high-performance workstations, 4K monitors, and fast storage."
                    st.session_state["tpl_budget"] = 38000
                    st.session_state["tpl_users"] = 10
                    st.session_state["tpl_location"] = "Kuala Lumpur"
                    st.session_state["tpl_reqs"] = "High-performance mini PCs\n4K monitors\nFast NVMe shared storage\nWireless keyboards and mice\nMicrosoft 365 licenses"
                    st.rerun()

        st.divider()
        b1, b2 = st.columns([3, 1])
        with b1:
            run_btn = st.button("⚡ Generate Solution", width="stretch", type="primary")
        with b2:
            clear_btn = st.button("Clear", width="stretch")

        if clear_btn:
            reset_state()
            st.rerun()

        if run_btn:
            errors = []
            if uses_text and not client_name.strip():
                errors.append("Client name is required.")
            if uses_text and not use_case.strip():
                errors.append("Project description is required.")
            if uses_image and uploaded_image is None:
                errors.append("Upload a brief image for image mode.")
            if errors:
                for error in errors:
                    st.error(error)
            else:
                reqs_list = [r.strip() for r in requirements.splitlines() if r.strip()]
                raw_brief = (
                    f"Client: {client_name}\n"
                    f"Use case: {use_case}\n"
                    f"Budget: MYR {budget_myr}\n"
                    f"Delivery location: {delivery_location}\n"
                    f"Number of users: {num_users}\n"
                    "Specific requirements:\n"
                    + "\n".join(f"- {r}" for r in reqs_list)
                )
                image_bytes = uploaded_image.getvalue() if uses_image and uploaded_image is not None else None
                image_media_type = uploaded_image.type if uses_image and uploaded_image is not None else None

                st.session_state.agent_steps = []
                st.session_state.pipeline_running = True
                st.session_state.pipeline_error = None
                st.session_state.report = None

                pipeline = SalesEngineerPipeline()

                def on_step(step: AgentStep) -> None:
                    st.session_state.agent_steps.append(step)

                try:
                    with st.spinner("Running four-agent pipeline..."):
                        report = pipeline.run(
                            raw_brief=raw_brief,
                            image_bytes=image_bytes,
                            image_media_type=image_media_type,
                            on_step=on_step,
                        )
                        st.session_state.report = report
                except Exception as exc:
                    st.session_state.pipeline_error = str(exc)
                finally:
                    st.session_state.pipeline_running = False
                st.rerun()

    with col_live:
        section_header("Pipeline Monitor")
        st.markdown(
            pipeline_tracker_html(st.session_state.agent_steps, st.session_state.pipeline_running),
            unsafe_allow_html=True,
        )
        render_step_feed()
        if st.session_state.pipeline_running:
            st.spinner("")
            time.sleep(1.5)
            st.rerun()
        if st.session_state.pipeline_error:
            st.error(f"Pipeline failed: {st.session_state.pipeline_error}")
        render_completion_card()


def render_empty_state(icon: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""
<div style="text-align:center;padding:64px 24px;color:var(--text-muted);">
  <div style="font-size:40px;margin-bottom:16px">{escape(icon)}</div>
  <div style="font-size:16px;font-weight:700;color:var(--text-secondary)">{escape(title)}</div>
  <div style="font-size:13px;margin-top:6px">{escape(subtitle)}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_report_tab() -> None:
    report = st.session_state.report
    if report is None:
        render_empty_state("📊", "No solution generated yet", "Go to New Brief and run the pipeline first")
        return

    metric_cols = st.columns(5)
    total_color = "bento-green" if report.within_budget else "bento-red"
    tech_color = "bento-green" if report.reviewer_feedback.technical_score >= 7 else "bento-amber"
    commercial_color = "bento-green" if report.reviewer_feedback.commercial_score >= 7 else "bento-amber"
    diversity = len(set(item.brand for item in report.line_items))
    cards = [
        bento_card_html("Total Quote", f"MYR {report.total_price_myr:,.0f}", f"{report.budget_utilization_pct:.1f}% of budget", total_color),
        bento_card_html("Budget", f"MYR {report.budget_myr:,.0f}", "Within budget ✓" if report.within_budget else "Over budget ✗"),
        bento_card_html("Technical Score", f"{report.reviewer_feedback.technical_score:.1f}/10", "DeepSeek-R1 review", tech_color),
        bento_card_html("Commercial Score", f"{report.reviewer_feedback.commercial_score:.1f}/10", "Value for money", commercial_color),
        bento_card_html("Vendor Diversity", f"{diversity} brands", f"across {len(report.line_items)} products", "bento-accent"),
    ]
    for col, card in zip(metric_cols, cards):
        with col:
            st.markdown(card, unsafe_allow_html=True)

    st.write("")
    status_cols = st.columns(5)
    source_label = {"text": "📝 Text", "image": "🖼️ Vision", "combined": "📝🖼️ Combined"}.get(report.brief_source, report.brief_source)
    statuses = [
        ("Budget", "pass" if report.within_budget else "fail"),
        ("Compatibility", "pass" if report.compatibility_matrix.all_compatible else "fail"),
        ("Delivery", "pass" if report.delivery_feasible else "fail"),
        ("Reviewer", "pass" if report.reviewer_feedback.approved else "fail"),
        (source_label, "info"),
    ]
    for col, (label, kind) in zip(status_cols, statuses):
        with col:
            st.markdown(badge(label, kind), unsafe_allow_html=True)

    section_header("Itemised Bill of Materials")
    line_items = report.line_items
    quote_df = pd.DataFrame(
        [
            {
                "Product": item.product_name,
                "Brand": item.brand,
                "Category": item.category,
                "Qty": item.quantity,
                "Unit Price (MYR)": money(item.unit_price_myr),
                "Subtotal (MYR)": money(item.subtotal_myr),
                "Shipping (MYR)": money(item.shipping_fee_myr),
                "SST (MYR)": money(item.sst_myr),
                "TCO (MYR)": money(item.tco_myr),
                "Confidence": item.confidence_score * 100,
                "URL": item.product_url,
            }
            for item in line_items
        ]
    )
    st.dataframe(
        quote_df,
        width="stretch",
        height=min(400, 60 + len(line_items) * 35),
        column_config={
            "Confidence": st.column_config.ProgressColumn("Confidence", min_value=0, max_value=100, format="%.0f%%"),
            "URL": st.column_config.LinkColumn("Link"),
        },
        hide_index=True,
    )
    totals = st.columns(4)
    totals[0].metric("Total Quote", money(report.total_price_myr))
    totals[1].metric("Total TCO", money(report.logistics_tco_total_myr))
    totals[2].metric("Total Shipping", money(sum(item.shipping_fee_myr for item in line_items)))
    totals[3].metric("Total SST", money(sum(item.sst_myr for item in line_items)))

    left, right = st.columns([0.6, 0.4], gap="large")
    with left:
        section_header("Executive Summary")
        st.markdown(f'<div class="glass-panel">{escape(report.executive_summary)}</div>', unsafe_allow_html=True)
        section_header("Reasoning Summary")
        st.markdown(f'<div class="glass-panel">{escape(report.reasoning_summary)}</div>', unsafe_allow_html=True)
    with right:
        section_header("Reviewer Assessment")
        st.caption("Technical Score")
        st.progress(min(max(report.reviewer_feedback.technical_score / 10, 0), 1))
        st.caption("Commercial Score")
        st.progress(min(max(report.reviewer_feedback.commercial_score / 10, 0), 1))
        st.markdown(
            badge("Approved" if report.reviewer_feedback.approved else "Needs Review", "pass" if report.reviewer_feedback.approved else "fail"),
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="glass-panel">{escape(report.reviewer_feedback.overall_assessment)}</div>',
            unsafe_allow_html=True,
        )
        for flag in report.reviewer_feedback.risk_flags:
            st.warning(flag)
        for suggestion in report.reviewer_feedback.suggestions:
            st.info(suggestion)

    section_header("Compatibility Matrix")
    compatibility_df = pd.DataFrame(
        [
            {
                "Product A": pair.get("a_name", pair["a"]),
                "Product B": pair.get("b_name", pair["b"]),
                "Compatible": "✅" if pair["compatible"] else "❌",
                "Reason": pair["reason"],
            }
            for pair in report.compatibility_matrix.pairs_checked
        ]
    )
    if compatibility_df.empty:
        st.info("No compatibility pairs were checked for this solution.")
    else:
        st.dataframe(compatibility_df, width="stretch", hide_index=True)

    history = report.self_critique_history
    with st.expander(f"🔄 Self-Critique Log ({len(history)} iterations)"):
        for item in history:
            c1, c2 = st.columns([1, 4])
            with c1:
                st.markdown(
                    badge("Pass ✅" if item.passed else "Fail ❌", "pass" if item.passed else "fail"),
                    unsafe_allow_html=True,
                )
            with c2:
                if item.issues_found:
                    st.markdown("**Issues**")
                    st.markdown("\n".join(f"- {escape(issue)}" for issue in item.issues_found))
                if item.improvements_made:
                    st.markdown("**Improvements**")
                    st.markdown("\n".join(f"- {escape(improvement)}" for improvement in item.improvements_made))

    section_header("Logistics")
    l1, l2 = st.columns(2)
    with l1:
        st.info(report.delivery_timeline_estimate)
    with l2:
        st.metric("Total TCO", money(report.logistics_tco_total_myr), delta="incl. shipping + SST")

    section_header("What-If Budget Analyser")
    st.caption(
        "Adjust the budget to instantly see how the solution changes — "
        "no need to re-run the full pipeline."
    )
    budget_delta_pct = st.slider(
        "Budget adjustment (%)",
        min_value=-30,
        max_value=50,
        value=0,
        step=5,
        format="%d%%",
    )
    if budget_delta_pct != 0 and st.session_state.report is not None:
        report = st.session_state.report
        adjusted_budget = report.budget_myr * (1 + budget_delta_pct / 100)
        product_ids = [item.product_id for item in report.line_items]
        quantities = {item.product_id: item.quantity for item in report.line_items}
        new_fit = calculate_budget_fit(product_ids, quantities, adjusted_budget)
        if new_fit.success:
            data = new_fit.data
            new_total = data["total_myr"]
            new_remaining = data["remaining_myr"]
            new_utilization = data["utilization_pct"]
            new_within = data["within_budget"]
            col1, col2, col3 = st.columns(3)
            col1.metric("Adjusted Budget", money(adjusted_budget), delta=f"{budget_delta_pct:+d}% vs original")
            col2.metric("Quote Total (unchanged)", money(new_total), delta=money(new_remaining) + " remaining")
            col3.metric(
                "Utilization at New Budget",
                pct(new_utilization),
                delta="Within budget ✅" if new_within else "Over budget ❌",
            )
            if not new_within:
                st.warning(
                    f"At MYR {adjusted_budget:,.0f}, the current quote exceeds the budget "
                    f"by MYR {abs(new_remaining):,.0f}. Consider reducing quantities or "
                    f"selecting lower-cost alternatives."
                )
            elif new_utilization < 60:
                st.info(
                    f"Budget utilization is only {new_utilization:.1f}%. "
                    f"You have MYR {new_remaining:,.0f} remaining — consider "
                    f"upgrading key components for better value."
                )
            else:
                st.success(f"Solution fits within the adjusted budget with {new_utilization:.1f}% utilization.")
        else:
            st.error(f"Budget analysis failed: {new_fit.error}")

    section_header("Export")
    d1, d2 = st.columns(2)
    safe_client = report.client_name.replace(" ", "_")
    with d1:
        try:
            pdf_bytes = generate_pdf(report)
            st.download_button(
                "📄 Download PDF Quote",
                data=pdf_bytes,
                file_name=f"quote_{safe_client}.pdf",
                mime="application/pdf",
                width="stretch",
            )
        except Exception as exc:
            st.error(f"PDF generation failed: {exc}")
    with d2:
        st.download_button(
            "📋 Download JSON Report",
            data=report.model_dump_json(indent=2),
            file_name=f"report_{safe_client}.json",
            mime="application/json",
            width="stretch",
        )


def render_reasoning_tab() -> None:
    report = st.session_state.report
    if report is None:
        render_empty_state("🔍", "No reasoning log yet", "Go to New Brief and run the pipeline first")
        return
    section_header("Full Agent Reasoning Log")
    f1, f2 = st.columns([2, 1])
    with f1:
        agent_filter = st.multiselect(
            "Filter by agent",
            ["VisualAnalyst", "Parser", "SalesEngineer", "Reviewer"],
            default=["VisualAnalyst", "Parser", "SalesEngineer", "Reviewer"],
            label_visibility="collapsed",
        )
    with f2:
        st.caption(f"{len(report.agent_steps)} total steps")

    filtered = [step for step in report.agent_steps if step.agent_name in agent_filter]
    for step in filtered:
        with st.expander(f"{step.agent_name} · Step {step.iteration} — {step.action[:65]}"):
            c1, c2 = st.columns([1, 2])
            with c1:
                st.markdown(f"**Agent:** {step.agent_name}")
                st.markdown(f"**Time:** {step.timestamp[11:19] if step.timestamp else ''}")
                if step.tool_called:
                    st.markdown(f"**Tool:** `{step.tool_called}`")
            with c2:
                st.markdown(f"**Result:** {step.tool_result_summary}")
                if step.tool_args:
                    with st.expander("Tool arguments"):
                        st.json(step.tool_args)


def render_catalog_tab() -> None:
    section_header("Product Catalog")
    categories = get_all_categories()
    f1, f2, f3, f4 = st.columns([2, 2, 1, 2])
    with f1:
        cat_filter = st.multiselect(
            "Categories",
            categories,
            default=categories,
            label_visibility="collapsed",
            placeholder="All categories",
        )
    with f2:
        max_price = st.slider("Max price (MYR)", 0, 15000, 15000, step=100, label_visibility="collapsed")
    with f3:
        in_stock = st.toggle("In stock", value=True)
    with f4:
        search_text = st.text_input("Search", placeholder="Search products...", label_visibility="collapsed")

    products = []
    for category_name in cat_filter or categories:
        products.extend(search_products(category=category_name, max_price=max_price, in_stock_only=in_stock))

    seen = set()
    unique_products = []
    for product in products:
        if product.id in seen:
            continue
        seen.add(product.id)
        if search_text.strip():
            needle = search_text.lower()
            if needle not in product.name.lower() and needle not in product.brand.lower():
                continue
        unique_products.append(product)

    if not unique_products:
        st.info("No products match the current filters.")
    else:
        df = pd.DataFrame(
            [
                {
                    "ID": product.id,
                    "Product": product.name,
                    "Brand": product.brand,
                    "Category": product.category,
                    "Price (MYR)": money(product.price_myr),
                    "In Stock": "✅" if product.in_stock else "❌",
                    "Regions": ", ".join(product.available_regions),
                    "URL": product.url,
                }
                for product in unique_products
            ]
        )
        st.dataframe(
            df,
            width="stretch",
            column_config={"URL": st.column_config.LinkColumn("Link")},
            hide_index=True,
        )
        st.caption(f"Showing {len(unique_products)} products")


inject_css()
catalog.init_db()

for key, value in {
    "report": None,
    "agent_steps": [],
    "pipeline_running": False,
    "pipeline_error": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = value

render_sidebar()
render_page_header()

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "🚀  New Brief",
        "📊  Solution Report",
        "🔍  Agent Reasoning",
        "📦  Catalog",
    ]
)

with tab1:
    render_new_brief_tab()
with tab2:
    render_report_tab()
with tab3:
    render_reasoning_tab()
with tab4:
    render_catalog_tab()
