"""Streamlit command-center frontend for AutoSales Engineer Pro."""

from __future__ import annotations

from html import escape
from typing import Iterable

import streamlit as st
from rich.console import Console

from core import catalog
from core.pdf_generator import generate_pdf
from pipeline import SalesEngineerPipeline

console = Console()

st.set_page_config(
    page_title="AutoSales Engineer Pro",
    page_icon="AE",
    layout="wide",
    initial_sidebar_state="collapsed",
)

catalog.init_db()

for key, value in {
    "report": None,
    "agent_steps": [],
    "pipeline_running": False,
    "visual_extraction": None,
    "pipeline_error": None,
    "view": "Command",
}.items():
    if key not in st.session_state:
        st.session_state[key] = value


def money(value: float) -> str:
    """Format Malaysian Ringgit consistently."""
    return "MYR {:,.2f}".format(value or 0.0)


def pct(value: float) -> str:
    """Format a percentage."""
    return "{:.1f}%".format(value or 0.0)


def short(text: str, length: int = 132) -> str:
    """Trim text for compact cards."""
    text = str(text or "")
    return text if len(text) <= length else text[: length - 1] + "..."


def html_list(items: Iterable[str], empty: str) -> str:
    """Render compact HTML bullet chips."""
    values = list(items) or [empty]
    return "".join(f"<div class='signal-item'>{escape(short(item, 150))}</div>" for item in values)


def inject_css() -> None:
    """Inject the high-impact command center theme."""
    st.markdown(
        """
<style>
:root {
  --bg0: #030712;
  --bg1: #07111f;
  --panel: rgba(12, 22, 38, 0.76);
  --panel2: rgba(16, 31, 52, 0.68);
  --line: rgba(125, 211, 252, 0.18);
  --text: #e5f7ff;
  --muted: #8ca5b8;
  --cyan: #22d3ee;
  --blue: #3b82f6;
  --green: #34d399;
  --orange: #fb923c;
  --red: #fb7185;
  --violet: #a78bfa;
}
html, body, [data-testid="stAppViewContainer"] {
  background:
    radial-gradient(circle at 18% 10%, rgba(34, 211, 238, .16), transparent 28rem),
    radial-gradient(circle at 78% 2%, rgba(167, 139, 250, .13), transparent 25rem),
    linear-gradient(135deg, var(--bg0) 0%, #08111f 48%, #020617 100%);
  color: var(--text);
}
[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"] { background: transparent; }
.block-container { padding: 1.1rem 2.1rem 3rem; max-width: 1500px; }
[data-testid="stSidebar"] { background: rgba(3, 7, 18, .92); border-right: 1px solid var(--line); }
h1, h2, h3, p, label, span, div { letter-spacing: 0 !important; }
.ae-shell {
  position: relative; overflow: hidden; border: 1px solid var(--line); border-radius: 22px;
  background: linear-gradient(140deg, rgba(15, 23, 42, .88), rgba(8, 15, 28, .72));
  box-shadow: 0 24px 80px rgba(0,0,0,.46), inset 0 0 0 1px rgba(255,255,255,.035);
}
.ae-shell:before {
  content:""; position:absolute; inset:0; pointer-events:none;
  background-image: linear-gradient(rgba(125,211,252,.075) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(125,211,252,.055) 1px, transparent 1px);
  background-size: 42px 42px; mask-image: linear-gradient(to bottom, black, transparent 78%);
}
.hero { position:relative; padding: 28px 30px 20px; }
.eyebrow { color: var(--cyan); font-size: 12px; text-transform: uppercase; font-weight: 800; }
.hero-title { margin: 4px 0 4px; font-size: clamp(38px, 6vw, 86px); line-height: .92; font-weight: 900; color: #f8fbff; }
.hero-title span { color: transparent; background: linear-gradient(90deg, var(--cyan), var(--green), var(--violet)); -webkit-background-clip: text; }
.hero-copy { max-width: 760px; color: #b7c7d6; font-size: 17px; line-height: 1.5; }
.hero-grid { display:grid; grid-template-columns: 1.15fr .85fr; gap: 20px; align-items: stretch; }
.pulse-map {
  min-height: 310px; border-left: 1px solid var(--line); position: relative; overflow:hidden;
  background: radial-gradient(circle at center, rgba(34,211,238,.12), transparent 42%);
}
.pulse-map:before { content:""; position:absolute; inset:15%; border: 1px solid rgba(34,211,238,.26); border-radius: 999px; animation: scan 3.4s infinite linear; }
.pulse-map:after { content:""; position:absolute; inset:31%; border: 1px solid rgba(52,211,153,.24); border-radius: 999px; animation: scan 2.5s infinite linear reverse; }
@keyframes scan { from { transform: scale(.72); opacity:.85; } to { transform: scale(1.35); opacity:.08; } }
.agent-node {
  position:absolute; width: 160px; padding: 12px; border: 1px solid rgba(125,211,252,.25);
  border-radius: 16px; background: rgba(2,6,23,.72); box-shadow: 0 0 28px rgba(34,211,238,.12);
}
.n0 { left: 8%; top: 16%; } .n1 { right: 9%; top: 22%; } .n2 { left: 15%; bottom: 16%; } .n3 { right: 7%; bottom: 13%; }
.agent-node b { display:block; color:#f8fbff; font-size: 13px; } .agent-node small { color: var(--muted); }
.metric-strip { display:grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 18px; }
.metric-card, .glass-card {
  border: 1px solid var(--line); border-radius: 18px; background: var(--panel);
  padding: 16px; box-shadow: inset 0 0 0 1px rgba(255,255,255,.03);
}
.metric-label { color: var(--muted); font-size: 12px; text-transform: uppercase; font-weight: 800; }
.metric-value { margin-top: 5px; color: #f8fbff; font-size: 25px; font-weight: 900; }
.nav-row { display:flex; gap: 10px; flex-wrap: wrap; margin: 18px 0; }
.stButton > button, .stDownloadButton > button {
  border-radius: 14px !important; border: 1px solid rgba(34,211,238,.32) !important;
  color: #e8fbff !important; background: linear-gradient(135deg, rgba(37,99,235,.72), rgba(8,145,178,.48)) !important;
  box-shadow: 0 10px 34px rgba(34,211,238,.14); font-weight: 800 !important;
}
.stButton > button:hover, .stDownloadButton > button:hover { transform: translateY(-1px); box-shadow: 0 18px 50px rgba(34,211,238,.22); }
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea, [data-testid="stNumberInput"] input, [data-baseweb="select"] {
  background: rgba(2, 6, 23, .62) !important; border-color: rgba(125,211,252,.22) !important; color: #e5f7ff !important;
}
.mission-grid { display:grid; grid-template-columns: minmax(340px, .84fr) minmax(440px, 1.16fr); gap: 18px; }
.agent-rail { display:grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.agent-chip {
  padding: 13px; border-radius: 16px; border: 1px solid var(--line); background: rgba(2,6,23,.55);
}
.agent-chip.done { border-color: rgba(52,211,153,.5); box-shadow: inset 0 -3px 0 rgba(52,211,153,.75); }
.agent-chip.pending { opacity: .62; }
.chip-kicker { color: var(--muted); font-size: 11px; text-transform: uppercase; }
.chip-title { color:#f8fbff; font-weight: 900; font-size: 14px; margin-top: 2px; }
.chip-model { color: var(--cyan); font-size: 12px; margin-top: 4px; }
.stream-card { padding: 12px 14px; margin-bottom: 10px; border-radius: 14px; background: rgba(2,6,23,.62); border: 1px solid rgba(125,211,252,.16); }
.stream-card b { color: #f8fbff; } .stream-card small { color: var(--muted); }
.quote-grid { display:grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
.product-card { min-height: 220px; border-radius: 18px; padding: 16px; background: linear-gradient(155deg, rgba(15,23,42,.86), rgba(8,47,73,.28)); border: 1px solid var(--line); }
.product-card h3 { color:#f8fbff; font-size: 18px; margin: 0 0 10px; }
.tag { display:inline-block; padding: 5px 8px; margin: 0 6px 7px 0; border: 1px solid rgba(34,211,238,.24); border-radius: 999px; color:#bbf7ff; font-size: 11px; background: rgba(34,211,238,.07); }
.price { color: var(--green); font-size: 24px; font-weight: 900; margin: 10px 0; }
.section-title { font-size: 25px; color:#f8fbff; font-weight: 900; margin: 18px 0 10px; }
.signal-item { padding: 10px 12px; margin-bottom: 8px; border-radius: 13px; background: rgba(2,6,23,.55); border: 1px solid rgba(125,211,252,.14); color:#dbeafe; }
.status-ok { color: var(--green); font-weight: 900; } .status-bad { color: var(--red); font-weight: 900; }
.catalog-grid { display:grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.catalog-card { border-radius:16px; padding:14px; background:rgba(2,6,23,.58); border:1px solid var(--line); min-height:170px; }
.catalog-card b { color:#f8fbff; } .catalog-card small { color: var(--muted); }
.pipeline-wrap { margin-top: 10px; display:grid; gap: 10px; }
.pipeline-stage {
    border: 1px solid var(--line);
    border-radius: 14px;
    padding: 12px 14px;
    background: rgba(2,6,23,.52);
    display: grid;
    grid-template-columns: 120px 1fr;
    align-items: center;
    column-gap: 12px;
}
.pipeline-state {
    display:inline-flex;
    align-items:center;
    justify-content:center;
    width: 108px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: .04em;
    padding: 6px 9px;
    border: 1px solid rgba(125,211,252,.20);
    color: #93c5fd;
    background: rgba(15,23,42,.72);
}
.pipeline-stage.running { border-color: rgba(52,211,153,.55); box-shadow: 0 0 0 1px rgba(52,211,153,.22); }
.pipeline-stage.running .pipeline-state { color: #052e16; background: #6ee7b7; border-color: #34d399; }
.pipeline-stage.done .pipeline-state { color: #052e16; background: #86efac; border-color: #4ade80; }
.pipeline-stage.pending .pipeline-state { color: #93c5fd; background: rgba(15,23,42,.72); border-color: rgba(125,211,252,.20); }
.pipeline-stage.blocked .pipeline-state { color: #3f0a12; background: #fda4af; border-color: #fb7185; }
.pipeline-main { color: #f8fbff; font-weight: 800; line-height: 1.2; }
.pipeline-sub { color: var(--muted); font-size: 12px; margin-top: 4px; }
.pipeline-live {
    margin-top: 12px;
    border: 1px solid var(--line);
    border-radius: 14px;
    padding: 12px 14px;
    background: rgba(2,6,23,.55);
}
.pipeline-live b { color: #f8fbff; }
.pipeline-live small { color: var(--muted); }

/* Full bright mode support for Streamlit light theme. */
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) {
    --bg0: #f6f9ff;
    --bg1: #edf3ff;
    --panel: rgba(255, 255, 255, 0.88);
    --panel2: rgba(248, 252, 255, 0.96);
    --line: rgba(30, 64, 175, 0.20);
    --text: #0f172a;
    --muted: #5b6d87;
    --cyan: #0284c7;
    --green: #059669;
    --violet: #7c3aed;
}
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) [data-testid="stAppViewContainer"] {
    background:
        radial-gradient(circle at 12% 8%, rgba(59, 130, 246, .14), transparent 30rem),
        radial-gradient(circle at 86% 0%, rgba(14, 165, 233, .12), transparent 26rem),
        linear-gradient(135deg, #f7fbff 0%, #edf4ff 46%, #eaf1ff 100%);
    color: var(--text);
}
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) [data-testid="stSidebar"] {
    background: rgba(241, 247, 255, .96);
    border-right: 1px solid var(--line);
}
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .ae-shell {
    background: linear-gradient(150deg, rgba(255,255,255,.96), rgba(242,248,255,.94));
    box-shadow: 0 20px 50px rgba(15, 23, 42, .10), inset 0 0 0 1px rgba(255,255,255,.65);
}
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .ae-shell:before {
    background-image: linear-gradient(rgba(14,165,233,.08) 1px, transparent 1px),
                                        linear-gradient(90deg, rgba(14,165,233,.06) 1px, transparent 1px);
}
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .pulse-map {
    background: radial-gradient(circle at center, rgba(14,165,233,.14), transparent 44%);
}
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .pulse-map:before {
    border-color: rgba(2,132,199,.28);
}
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .pulse-map:after {
    border-color: rgba(5,150,105,.24);
}
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .agent-node {
    background: rgba(255,255,255,.95);
    border-color: rgba(30,64,175,.20);
    box-shadow: 0 8px 26px rgba(30, 64, 175, .08);
}
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .agent-node b,
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .chip-title,
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .section-title,
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .metric-value,
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .hero-title,
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .signal-item,
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .stream-card b,
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .product-card h3,
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .catalog-card b {
    color: #0f172a !important;
}
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .agent-node small,
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .hero-copy,
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .metric-label,
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .chip-kicker,
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .stream-card small,
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .catalog-card small {
    color: #475569 !important;
}
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .glass-card,
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .metric-card,
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .agent-chip,
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .stream-card,
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .signal-item,
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .catalog-card,
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .product-card,
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .pipeline-stage,
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .pipeline-live {
    background: var(--panel2) !important;
    border-color: rgba(30, 64, 175, .16) !important;
}
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .product-card {
    background: linear-gradient(145deg, rgba(255,255,255,.98), rgba(239,247,255,.92)) !important;
}
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .tag {
    color: #0c4a6e;
    background: rgba(14,165,233,.10);
    border-color: rgba(14,165,233,.28);
}
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .price {
    color: #047857;
}
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .pipeline-main,
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .pipeline-live b {
    color: #0f172a !important;
}
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .pipeline-sub,
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .pipeline-live small {
    color: #475569 !important;
}
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .pipeline-state {
    color: #1e3a8a;
    background: rgba(219, 234, 254, .9);
    border-color: rgba(30, 64, 175, .20);
}
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .stButton > button,
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .stDownloadButton > button {
    color: #ffffff !important;
    border-color: rgba(2,132,199,.35) !important;
    background: linear-gradient(135deg, #2563eb, #0ea5e9) !important;
    box-shadow: 0 10px 26px rgba(37, 99, 235, .22) !important;
}
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .stButton > button:hover,
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) .stDownloadButton > button:hover {
    box-shadow: 0 14px 34px rgba(37, 99, 235, .28) !important;
}
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) [data-testid="stTextInput"] input,
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) [data-testid="stTextArea"] textarea,
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) [data-testid="stNumberInput"] input,
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) [data-baseweb="select"],
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) [data-baseweb="base-input"] {
    background: #ffffff !important;
    border-color: rgba(30,64,175,.24) !important;
    color: #0f172a !important;
}
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) [data-baseweb="popover"],
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) [role="listbox"] {
    background: #ffffff !important;
    color: #0f172a !important;
}
:is(html[data-theme="light"], body[data-theme="light"], [data-theme="light"]) [data-testid="stFileUploaderDropzone"] {
    background: #ffffff;
    border-color: rgba(30,64,175,.24);
}

@media (prefers-color-scheme: light) {
    :root {
        --bg0: #f6f9ff;
        --bg1: #edf3ff;
        --panel: rgba(255, 255, 255, 0.88);
        --panel2: rgba(248, 252, 255, 0.96);
        --line: rgba(30, 64, 175, 0.20);
        --text: #0f172a;
        --muted: #5b6d87;
        --cyan: #0284c7;
        --green: #059669;
        --violet: #7c3aed;
    }
    html, body, [data-testid="stAppViewContainer"] {
        background:
            radial-gradient(circle at 12% 8%, rgba(59, 130, 246, .14), transparent 30rem),
            radial-gradient(circle at 86% 0%, rgba(14, 165, 233, .12), transparent 26rem),
            linear-gradient(135deg, #f7fbff 0%, #edf4ff 46%, #eaf1ff 100%);
        color: var(--text);
    }
    [data-testid="stSidebar"] { background: rgba(241, 247, 255, .96); border-right: 1px solid var(--line); }
    .ae-shell {
        background: linear-gradient(150deg, rgba(255,255,255,.96), rgba(242,248,255,.94));
        box-shadow: 0 20px 50px rgba(15, 23, 42, .10), inset 0 0 0 1px rgba(255,255,255,.65);
    }
    .ae-shell:before {
        background-image: linear-gradient(rgba(14,165,233,.08) 1px, transparent 1px),
                                            linear-gradient(90deg, rgba(14,165,233,.06) 1px, transparent 1px);
    }
    .pulse-map { background: radial-gradient(circle at center, rgba(14,165,233,.14), transparent 44%); }
    .pulse-map:before { border-color: rgba(2,132,199,.28); }
    .pulse-map:after { border-color: rgba(5,150,105,.24); }
    .agent-node {
        background: rgba(255,255,255,.95);
        border-color: rgba(30,64,175,.20);
        box-shadow: 0 8px 26px rgba(30,64,175,.08);
    }
    .agent-node b, .chip-title, .section-title, .metric-value, .hero-title, .signal-item, .stream-card b, .product-card h3, .catalog-card b { color: #0f172a !important; }
    .agent-node small, .hero-copy, .metric-label, .chip-kicker, .stream-card small, .catalog-card small { color: #475569 !important; }
    .glass-card, .metric-card, .agent-chip, .stream-card, .signal-item, .catalog-card, .product-card {
        background: var(--panel2) !important;
        border-color: rgba(30, 64, 175, .16) !important;
    }
    .pipeline-stage, .pipeline-live {
        background: var(--panel2) !important;
        border-color: rgba(30, 64, 175, .16) !important;
    }
    .pipeline-main, .pipeline-live b { color: #0f172a !important; }
    .pipeline-sub, .pipeline-live small { color: #475569 !important; }
    .pipeline-state {
        color: #1e3a8a;
        background: rgba(219, 234, 254, .9);
        border-color: rgba(30, 64, 175, .20);
    }
    .product-card { background: linear-gradient(145deg, rgba(255,255,255,.98), rgba(239,247,255,.92)) !important; }
    .tag { color: #0c4a6e; background: rgba(14,165,233,.10); border-color: rgba(14,165,233,.28); }
    .price { color: #047857; }
    .stButton > button, .stDownloadButton > button {
        color: #ffffff !important;
        border-color: rgba(2,132,199,.35) !important;
        background: linear-gradient(135deg, #2563eb, #0ea5e9) !important;
        box-shadow: 0 10px 26px rgba(37, 99, 235, .22) !important;
    }
    .stButton > button:hover, .stDownloadButton > button:hover { box-shadow: 0 14px 34px rgba(37, 99, 235, .28) !important; }
    [data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea, [data-testid="stNumberInput"] input, [data-baseweb="select"], [data-baseweb="base-input"] {
        background: #ffffff !important;
        border-color: rgba(30,64,175,.24) !important;
        color: #0f172a !important;
    }
    [data-baseweb="popover"], [role="listbox"] { background: #ffffff !important; color: #0f172a !important; }
    [data-testid="stFileUploaderDropzone"] { background: #ffffff; border-color: rgba(30,64,175,.24); }
}

@media (max-width: 1000px) {
  .hero-grid, .mission-grid, .quote-grid, .catalog-grid, .metric-strip, .agent-rail { grid-template-columns: 1fr; }
  .pulse-map { min-height: 260px; border-left: 0; border-top: 1px solid var(--line); }
}
</style>
        """,
        unsafe_allow_html=True,
    )


def render_shell_open() -> None:
    """Open the main visual shell."""
    st.markdown("<div class='ae-shell'>", unsafe_allow_html=True)


def render_shell_close() -> None:
    """Close the main visual shell."""
    st.markdown("</div>", unsafe_allow_html=True)


def render_hero() -> None:
    """Render the first ten seconds of the demo."""
    stats = catalog.get_catalog_stats()
    report = st.session_state.report
    total = money(report.total_price_myr) if report else "Awaiting launch"
    score = f"{report.reviewer_feedback.technical_score:.1f}/10" if report else "DeepSeek standby"
    st.markdown(
        f"""
<div class="hero">
  <div class="hero-grid">
    <div>
      <div class="eyebrow">Autonomous technical sales command center</div>
      <div class="hero-title">AutoSales<br><span>Engineer Pro</span></div>
      <div class="hero-copy">
        A four-agent procurement engine that sees client briefs, parses intent, builds a compatible Malaysian IT quote,
        critiques itself, and submits to a senior AI reviewer. The demo impact screen is the live agent console below.
      </div>
      <div class="metric-strip">
        <div class="metric-card"><div class="metric-label">Catalog</div><div class="metric-value">{stats["total_products"]}</div></div>
        <div class="metric-card"><div class="metric-label">Providers</div><div class="metric-value">2</div></div>
        <div class="metric-card"><div class="metric-label">Quote</div><div class="metric-value">{escape(total)}</div></div>
        <div class="metric-card"><div class="metric-label">Review</div><div class="metric-value">{escape(score)}</div></div>
      </div>
    </div>
    <div class="pulse-map">
      <div class="agent-node n0"><b>Gemini 3.5</b><small>Vision with 2.5 fallback</small></div>
      <div class="agent-node n1"><b>Groq</b><small>Brief parser</small></div>
      <div class="agent-node n2"><b>Qwen / Groq</b><small>Solution builder fallback</small></div>
      <div class="agent-node n3"><b>DeepSeek / Groq</b><small>Senior review fallback</small></div>
    </div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_nav() -> str:
    """Render the high-level view selector."""
    options = ["Command", "Quote", "Reasoning", "Catalog"]
    cols = st.columns(len(options))
    for col, option in zip(cols, options):
        with col:
            if st.button(option, use_container_width=True, type="primary" if st.session_state.view == option else "secondary"):
                st.session_state.view = option
                st.rerun()
    return st.session_state.view


def build_raw_brief() -> str:
    """Create the text brief from form fields."""
    requirements = st.session_state.get("requirements", "")
    return f"""
Client: {st.session_state.get("client_name", "")}
Use case: {st.session_state.get("use_case", "")}
Budget: MYR {st.session_state.get("budget_myr", 0):,.2f}
Delivery location: {st.session_state.get("delivery_location", "")}
Number of users: {st.session_state.get("num_users", "")}
Specific requirements:
{requirements}
""".strip()


def set_template(name: str) -> None:
    """Populate form fields with a quick template."""
    templates = {
        "office": {
            "client_name": "Acme KL Services",
            "use_case": "New office launch for 15 staff requiring secure internet, WiFi coverage, file sharing, Microsoft 365, UPS protection, and a polished meeting room.",
            "budget_myr": 25000,
            "delivery_location": "Kuala Lumpur",
            "num_users": 15,
            "requirements": "WiFi coverage for 3 floors\nNAS for shared files\nUPS backup power\nMicrosoft 365 for all users\nVideo conferencing room setup",
        },
        "server": {
            "client_name": "Penang Precision Manufacturing",
            "use_case": "SME server room refresh for 50 users with secure firewall, rack compute, backup storage, switching, WiFi, and protected power.",
            "budget_myr": 85000,
            "delivery_location": "Penang",
            "num_users": 50,
            "requirements": "Rack server for business apps\nFirewall with VPN\nNAS backup\nUPS and rack\nScalable switching and WiFi",
        },
        "studio": {
            "client_name": "Kuching Creative Studio",
            "use_case": "Creative studio collaboration setup for 10 users with compact desktops, premium displays, peripherals, cloud productivity, and backup.",
            "budget_myr": 38000,
            "delivery_location": "Kuching",
            "num_users": 10,
            "requirements": "Compact desktops\n4K displays\nKeyboard and mouse sets\nTeams and OneDrive\nBackup storage",
        },
    }
    for field, value in templates[name].items():
        st.session_state[field] = value


def render_sidebar() -> None:
    """Render compact operator controls."""
    with st.sidebar:
        st.markdown("## AE Pro")
        st.caption("Four-agent command console")
        st.divider()
        st.markdown("**Pipeline**")
        st.caption("Gemini 3.5 -> Gemini 2.5 fallback -> Groq -> Chutes/Groq")
        st.divider()
        stats = catalog.get_catalog_stats()
        st.metric("Products", stats["total_products"])
        st.metric("Categories", len(stats["categories"]))
        st.caption(f"Range: {money(stats['min_price'])} - {money(stats['max_price'])}")
        st.divider()
        st.toggle("Debug telemetry", key="debug_mode", value=False)


def run_pipeline(uses_text: bool, uses_image: bool, uploaded_image) -> None:
    """Validate input and run the pipeline."""
    if uses_text and (not st.session_state.get("client_name") or not st.session_state.get("use_case")):
        st.error("Client name and use case are required for text briefs.")
        return
    if uses_image and uploaded_image is None:
        st.error("Upload a supported image for visual extraction.")
        return
    st.session_state.pipeline_running = True
    st.session_state.agent_steps = []
    st.session_state.pipeline_error = None
    try:
        raw_brief = build_raw_brief() if uses_text else ""
        image_bytes = uploaded_image.getvalue() if uploaded_image else None
        media_type = uploaded_image.type if uploaded_image else None
        launch = st.empty()
        launch.markdown(
            """
<div class="glass-card">
  <div class="eyebrow">Live orchestration started</div>
  <div class="section-title">Agents are negotiating the solution...</div>
  <div class="signal-item">Vision, parsing, catalog search, compatibility, budget, delivery, critique, and senior review are running.</div>
</div>
            """,
            unsafe_allow_html=True,
        )
        pipeline = SalesEngineerPipeline()
        report = pipeline.run(
            raw_brief=raw_brief,
            image_bytes=image_bytes,
            image_media_type=media_type,
            on_step=lambda step: st.session_state.agent_steps.append(step),
        )
        st.session_state.report = report
        st.session_state.view = "Quote"
        st.success("Mission complete. Quote package generated.")
    except RuntimeError as exc:
        console.log(f"[red]{exc}[/red]")
        st.session_state.pipeline_error = str(exc)
        st.error(str(exc))
    except Exception as exc:
        console.log(f"[red]Pipeline failed: {exc}[/red]")
        st.session_state.pipeline_error = str(exc)
        st.error(f"Pipeline failed after {len(st.session_state.agent_steps)} logged steps: {exc}")
    finally:
        st.session_state.pipeline_running = False


def render_agent_rail() -> None:
    """Show a clean pipeline monitor with one row per agent."""
    steps = st.session_state.agent_steps
    latest_by_agent = {}
    for step in steps:
        latest_by_agent[step.agent_name] = step
    done_agents = set(latest_by_agent.keys())
    latest_agent = steps[-1].agent_name if steps else None
    pipeline_error = st.session_state.pipeline_error
    running = st.session_state.pipeline_running
    agents = [
        ("VisualAnalyst", "Visual intake", "Gemini 3.5 -> 2.5"),
        ("Parser", "Requirements parser", "Groq Llama 3.3 70B"),
        ("SalesEngineer", "Solution builder", "Chutes Qwen -> Groq"),
        ("Reviewer", "Final QA", "Chutes DeepSeek -> Groq"),
    ]
    rows = []
    for idx, (name, label, model) in enumerate(agents):
        if running and latest_agent == name:
            state = "running"
            badge = "Running"
        elif pipeline_error and latest_agent == name:
            state = "blocked"
            badge = "Blocked"
        elif name in done_agents:
            state = "done"
            badge = "Done"
        else:
            previous_done = all(prev_name in done_agents for prev_name, _, _ in agents[:idx])
            state = "pending"
            badge = "Queued" if previous_done else "Waiting"

        latest = latest_by_agent.get(name)
        detail = latest.action if latest else "Awaiting pipeline start"
        summary = latest.tool_result_summary if latest else model
        rows.append(
            "<div class='pipeline-stage {state}'>"
            "<div><span class='pipeline-state'>{badge}</span></div>"
            "<div>"
            "<div class='pipeline-main'>{name} • {label}</div>"
            "<div class='pipeline-sub'>{detail}</div>"
            "<div class='pipeline-sub'>{summary}</div>"
            "</div></div>".format(
                state=state,
                badge=escape(badge),
                name=escape(name),
                label=escape(label),
                detail=escape(short(detail, 100)),
                summary=escape(short(summary, 120)),
            )
        )
    st.markdown(f"<div class='pipeline-wrap'>{''.join(rows)}</div>", unsafe_allow_html=True)


def render_step_stream() -> None:
    """Render a concise live pipeline snapshot."""
    steps = st.session_state.agent_steps
    if not steps:
        st.markdown(
            "<div class='pipeline-live'><b>Pipeline idle</b><br><small>Launch a mission to see the active agent and latest pipeline action.</small></div>",
            unsafe_allow_html=True,
        )
        return
    latest = steps[-1]
    active_text = "Running" if st.session_state.pipeline_running else "Last update"
    st.markdown(
        f"""
<div class="pipeline-live">
  <b>{escape(active_text)}: {escape(latest.agent_name)}</b><br>
  <small>{escape(short(latest.action, 130))}</small><br>
  <small>{escape(latest.tool_called or "no tool")} | {escape(short(latest.tool_result_summary, 140))} | {escape(latest.timestamp[-8:])}</small>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_command_view() -> None:
    """Render the demo-first command center."""
    st.markdown("<div class='mission-grid'>", unsafe_allow_html=True)
    left, right = st.columns([0.42, 0.58])
    with left:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("<div class='eyebrow'>Mission input</div><div class='section-title'>Brief cockpit</div>", unsafe_allow_html=True)
        mode = st.radio("Intake mode", ["Text", "Image", "Both"], horizontal=True, label_visibility="collapsed")
        uses_text = mode in {"Text", "Both"}
        uses_image = mode in {"Image", "Both"}
        uploaded_image = None
        if uses_text:
            st.text_input("Client Name", key="client_name", placeholder="Acme KL Services")
            st.text_area("Use Case", height=118, key="use_case", placeholder="New office setup for 20 staff with secure internet, WiFi, NAS, UPS, and conferencing.")
            c1, c2 = st.columns(2)
            c1.number_input("Budget (MYR)", min_value=1000, max_value=1000000, value=st.session_state.get("budget_myr", 25000), step=1000, key="budget_myr")
            c2.number_input("Users", min_value=1, max_value=10000, value=st.session_state.get("num_users", 15), key="num_users")
            st.selectbox("Delivery Location", ["Kuala Lumpur", "Penang", "Johor Bahru", "Kota Kinabalu", "Kuching", "Nationwide"], key="delivery_location")
            st.text_area("Requirements", height=114, key="requirements", placeholder="One requirement per line")
        if uses_image:
            uploaded_image = st.file_uploader("Visual brief", type=["jpg", "jpeg", "png", "webp"])
            if uploaded_image:
                st.image(uploaded_image, caption="Gemini visual extraction target", use_container_width=True)
        st.markdown("<div class='eyebrow'>Instant demos</div>", unsafe_allow_html=True)
        t1, t2, t3 = st.columns(3)
        t1.button("Office", on_click=set_template, args=("office",), use_container_width=True)
        t2.button("Server Room", on_click=set_template, args=("server",), use_container_width=True)
        t3.button("Studio", on_click=set_template, args=("studio",), use_container_width=True)
        a, b = st.columns([0.7, 0.3])
        if a.button("Launch Agent Swarm", type="primary", use_container_width=True):
            run_pipeline(uses_text, uses_image, uploaded_image)
        if b.button("Reset", use_container_width=True):
            st.session_state.report = None
            st.session_state.agent_steps = []
            st.session_state.pipeline_error = None
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with right:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("<div class='eyebrow'>Live status</div><div class='section-title'>Pipeline monitor</div>", unsafe_allow_html=True)
        render_agent_rail()
        render_step_stream()
        if st.session_state.pipeline_error:
            st.error(st.session_state.pipeline_error)
        if st.session_state.report:
            report = st.session_state.report
            st.markdown(
                f"""
<div class="metric-strip">
  <div class="metric-card"><div class="metric-label">Subtotal</div><div class="metric-value">{money(report.total_price_myr)}</div></div>
  <div class="metric-card"><div class="metric-label">Budget fit</div><div class="metric-value">{pct(report.budget_utilization_pct)}</div></div>
  <div class="metric-card"><div class="metric-label">Tech score</div><div class="metric-value">{report.reviewer_feedback.technical_score:.1f}/10</div></div>
  <div class="metric-card"><div class="metric-label">TCO</div><div class="metric-value">{money(report.logistics_tco_total_myr)}</div></div>
</div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def render_quote_view() -> None:
    """Render the cinematic quote package."""
    report = st.session_state.report
    if report is None:
        st.markdown("<div class='glass-card'><div class='section-title'>No quote package yet</div><div class='signal-item'>Run a mission from Command to generate the judge-facing proposal.</div></div>", unsafe_allow_html=True)
        return
    safe_client = "".join(ch for ch in report.client_name.lower().replace(" ", "_") if ch.isalnum() or ch == "_")
    st.markdown(
        f"""
<div class="glass-card">
  <div class="eyebrow">Generated proposal</div>
  <div class="section-title">{escape(report.client_name)}</div>
  <div class="metric-strip">
    <div class="metric-card"><div class="metric-label">Subtotal</div><div class="metric-value">{money(report.total_price_myr)}</div></div>
    <div class="metric-card"><div class="metric-label">Grand TCO</div><div class="metric-value">{money(report.logistics_tco_total_myr)}</div></div>
    <div class="metric-card"><div class="metric-label">Budget use</div><div class="metric-value">{pct(report.budget_utilization_pct)}</div></div>
    <div class="metric-card"><div class="metric-label">Reviewer</div><div class="metric-value">{report.reviewer_feedback.technical_score:.1f}/{report.reviewer_feedback.commercial_score:.1f}</div></div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<div class='section-title'>Itemized bill of materials</div>", unsafe_allow_html=True)
    cards = []
    for item in report.line_items:
        cards.append(
            f"""
<div class="product-card">
  <span class="tag">{escape(item.category)}</span><span class="tag">{escape(item.source_platform)}</span>
  <h3>{escape(item.product_name)}</h3>
  <div class="price">{money(item.subtotal_myr)}</div>
  <div class="signal-item">Qty {item.quantity} x {money(item.unit_price_myr)}</div>
  <div class="signal-item">Confidence {item.confidence_score:.0%}: {escape(short(item.confidence_reason, 90))}</div>
  <small>{escape(short(item.product_url, 95))}</small>
</div>
            """
        )
    st.markdown(f"<div class='quote-grid'>{''.join(cards)}</div>", unsafe_allow_html=True)
    q1, q2 = st.columns([0.52, 0.48])
    with q1:
        st.markdown("<div class='section-title'>Logistics and ownership</div>", unsafe_allow_html=True)
        tco = "".join(
            f"<div class='signal-item'><b>{escape(item.product_name)}</b><br>Shipping {money(item.shipping_fee_myr)} | SST {money(item.sst_myr)} | TCO <span class='status-ok'>{money(item.tco_myr)}</span></div>"
            for item in report.line_items
        )
        st.markdown(f"<div class='glass-card'>{tco}<div class='metric-card'><div class='metric-label'>Grand total TCO</div><div class='metric-value'>{money(report.logistics_tco_total_myr)}</div></div></div>", unsafe_allow_html=True)
    with q2:
        st.markdown("<div class='section-title'>Executive intelligence</div>", unsafe_allow_html=True)
        st.markdown(
            f"""
<div class="glass-card">
  <div class="signal-item">{escape(report.executive_summary)}</div>
  <div class="signal-item"><b>Reasoning:</b> {escape(report.reasoning_summary)}</div>
  <div class="signal-item"><b>Delivery:</b> {escape(report.delivery_timeline_estimate)}</div>
</div>
            """,
            unsafe_allow_html=True,
        )
    r1, r2, r3 = st.columns(3)
    r1.markdown(f"<div class='glass-card'><div class='metric-label'>Budget</div><div class='metric-value'>{'PASS' if report.within_budget else 'ALERT'}</div></div>", unsafe_allow_html=True)
    r2.markdown(f"<div class='glass-card'><div class='metric-label'>Compatibility</div><div class='metric-value'>{'PASS' if report.compatibility_matrix.all_compatible else 'ALERT'}</div></div>", unsafe_allow_html=True)
    r3.markdown(f"<div class='glass-card'><div class='metric-label'>Delivery</div><div class='metric-value'>{'PASS' if report.delivery_feasible else 'ALERT'}</div></div>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>Senior reviewer signals</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.markdown(f"<div class='glass-card'><div class='eyebrow'>Risk flags</div>{html_list(report.reviewer_feedback.risk_flags, 'No major risk flags')}</div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='glass-card'><div class='eyebrow'>Suggestions</div>{html_list(report.reviewer_feedback.suggestions, 'No additional suggestions')}</div>", unsafe_allow_html=True)
    d1, d2 = st.columns(2)
    d1.download_button("Download PDF Quote", data=generate_pdf(report), file_name=f"quote_{safe_client}.pdf", mime="application/pdf", use_container_width=True)
    d2.download_button("Download JSON Report", data=report.model_dump_json(indent=2), file_name=f"report_{safe_client}.json", mime="application/json", use_container_width=True)


def render_reasoning_view() -> None:
    """Render full traceability without boring expanders as the primary experience."""
    report = st.session_state.report
    if report is None:
        st.markdown("<div class='glass-card'><div class='section-title'>Reasoning stream idle</div><div class='signal-item'>Run the pipeline to unlock the audit trail.</div></div>", unsafe_allow_html=True)
        return
    selected_agents = st.multiselect("Filter agents", ["VisualAnalyst", "Parser", "SalesEngineer", "Reviewer"], default=["VisualAnalyst", "Parser", "SalesEngineer", "Reviewer"])
    for step in report.agent_steps:
        if step.agent_name not in selected_agents:
            continue
        st.markdown(
            f"""
<div class="stream-card">
  <b>{escape(step.agent_name)} / iteration {step.iteration}</b><br>
  <span>{escape(step.action)}</span><br>
  <small>Tool: {escape(step.tool_called or "N/A")} | {escape(step.timestamp)}</small>
  <div class="signal-item">{escape(step.tool_result_summary)}</div>
</div>
            """,
            unsafe_allow_html=True,
        )
        if step.tool_args and st.session_state.get("debug_mode"):
            st.json(step.tool_args)
    if st.session_state.get("debug_mode"):
        st.json(report.model_dump())


def render_catalog_view() -> None:
    """Render the product catalog as a visual arsenal."""
    products = catalog.search_products(in_stock_only=False)
    f1, f2, f3, f4 = st.columns(4)
    categories = f1.multiselect("Category", catalog.get_all_categories())
    max_price = f2.slider("Max price", 0, 50000, 50000, 500)
    in_stock_only = f3.toggle("In stock only", value=True)
    text_search = f4.text_input("Search")
    filtered = []
    for product in products:
        if categories and product.category not in categories:
            continue
        if product.price_myr > max_price:
            continue
        if in_stock_only and not product.in_stock:
            continue
        if text_search and text_search.lower() not in f"{product.name} {product.brand}".lower():
            continue
        filtered.append(product)
    cards = []
    for product in filtered[:40]:
        cards.append(
            f"""
<div class="catalog-card">
  <span class="tag">{escape(product.category)}</span>
  <b>{escape(product.name)}</b><br>
  <small>{escape(product.brand)} | {escape(", ".join(product.available_regions))}</small>
  <div class="price">{money(product.price_myr)}</div>
  <small>{escape(short(product.url, 95))}</small>
</div>
            """
        )
    st.markdown(f"<div class='catalog-grid'>{''.join(cards)}</div>", unsafe_allow_html=True)


inject_css()
render_sidebar()
render_shell_open()
render_hero()
st.markdown("<div style='padding: 0 30px 30px'>", unsafe_allow_html=True)
view = render_nav()
if view == "Command":
    render_command_view()
elif view == "Quote":
    render_quote_view()
elif view == "Reasoning":
    render_reasoning_view()
else:
    render_catalog_view()
st.markdown("</div>", unsafe_allow_html=True)
render_shell_close()
