# AutoSales Engineer Pro

AutoSales Engineer Pro is a Streamlit application for AI-assisted IT sales engineering. It turns a client brief or image into a structured solution, validates the result through multiple agents, and produces a quote-ready report with supporting rationale.

## Overview

The application runs a four-agent pipeline:

```text
Client Text / Image
    |
    v
Visual Analyst  ->  Parser  ->  Sales Engineer  ->  Reviewer
(Gemini)            (Groq)      (Chutes / Groq)     (Chutes / Groq)
    |                |              |                 |
    +----------------+--------------+-----------------+
                 |
                 v
               Streamlit report + PDF quote
```

Each stage adds structure and validation:

- The Visual Analyst extracts text and context from uploaded images.
- The Parser converts raw brief data into a structured procurement brief.
- The Sales Engineer designs a compatible solution using tools and catalog data.
- The Reviewer performs a final quality and commercial review before delivery.

## Key Features

- Image-to-brief extraction for whiteboards, RFQs, diagrams, and server-room photos.
- Structured procurement parsing for Malaysian IT sales workflows.
- Tool-assisted solution generation with catalog search, compatibility checks, budget fit, and delivery validation.
- Self-critique and reviewer feedback loops for higher-quality outputs.
- Local SQLite catalog fallback for resilient offline or provider-limited operation.
- Optional web product search when `TAVILY_API_KEY` is available.
- Professional quote export with line items, totals, reasoning, and delivery estimates.
- Clean Streamlit dashboard with a live pipeline monitor.

## Technology Stack

- Python 3.10+
- Streamlit
- OpenAI-compatible provider clients
- Pydantic
- Rich
- ReportLab
- SQLite
- Tavily search integration

## Prerequisites

- Python 3.10 or later (3.11 recommended)
- pip 23+
- Git

## Quick Start — Windows

```bash
git clone https://github.com/yourrepo/autosales-engineer-pro
cd autosales-engineer-pro
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Open .env in a text editor and fill in your API keys
streamlit run main.py
```

## Quick Start — macOS / Linux

```bash
git clone https://github.com/yourrepo/autosales-engineer-pro
cd autosales-engineer-pro
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Open .env in a text editor and fill in your API keys
streamlit run main.py
```

## Minimum Required API Keys

Only two keys are required. All other providers degrade gracefully.

| Key | Required | Used For |
|---|---|---|
| CHUTES_API_KEY | ✅ Yes | Sales Engineer (Qwen 2.5 72B) + Reviewer (DeepSeek-R1) |
| GROQ_API_KEY | ✅ Yes | Parser (Llama 3.3 70B) + all provider fallbacks |
| GEMINI_API_KEY | Optional | Vision agent (image upload feature) |
| TAVILY_API_KEY | Optional | Real web product search with live URLs |

## First Run

On first launch `catalog.db` is created and seeded automatically
with 40 products across 8 categories. No manual database setup
is required. The file is gitignored and recreated if deleted.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: google.genai` | `pip install google-genai>=1.0.0` |
| `catalog.db locked` | Delete `catalog.db` and restart Streamlit |
| Chutes API 429 / rate limit | Pipeline auto-falls back to Groq; no action needed |
| Vision upload not working | Add `GEMINI_API_KEY` to `.env` |
| Tavily returns no results | Normal; pipeline uses SQLite catalog fallback |
| `RuntimeError: Missing Chutes AI key` | Add `CHUTES_API_KEY` to `.env` |
| Streamlit hangs during pipeline | Each API call has a 60s timeout; wait or restart |

## How To Use

1. Open the app in Streamlit.
2. Choose an intake mode: text, image, or both.
3. Enter the client brief or upload an image.
4. Launch the agent pipeline.
5. Review the generated quote, reasoning, and PDF output.

## Example Text Brief

```text
Client: Acme KL Services
Use case: New office setup for 15 staff with secure internet, WiFi, file sharing, Microsoft 365, and video conferencing.
Budget: MYR 25,000
Delivery location: Kuala Lumpur
Number of users: 15
Specific requirements:
- WiFi coverage for 3 floors
- NAS for shared files
- UPS backup power
- Microsoft 365 for all users
- Video conferencing room setup
```

## Example Image Briefs

Useful uploads include:

- A whiteboard photo listing budget, users, office location, and device needs.
- A scanned RFQ document with procurement requirements.
- A hand-drawn network diagram with router, switch, AP, firewall, and NAS labels.
- A photo of an existing server room or network rack.

## Pipeline Behavior

The pipeline is designed to stay resilient when provider limits or tool failures occur:

- The Sales Engineer can fall back to a deterministic local catalog builder.
- Groq prompts are compacted to reduce request-size and TPM issues.
- The Reviewer can use a fallback path if the primary provider is unavailable.
- The UI shows a clean live pipeline monitor so you can see which agent is active.

## Output

The generated report and PDF include:

- Itemized bill of materials with quantity, unit price, product URL, and source platform.
- Logistics and cost-of-ownership figures, including shipping and SST.
- A reasoning summary describing the solution choices.
- A delivery timeline estimate for the selected region.
- Reviewer feedback with technical and commercial scores.

## Project Structure

```text
autosales-engineer-pro/
├── main.py
├── pipeline.py
├── agents/
│   ├── __init__.py
│   ├── visual_analyst_agent.py
│   ├── parser_agent.py
│   ├── sales_engineer_agent.py
│   └── reviewer_agent.py
├── core/
│   ├── __init__.py
│   ├── catalog.py
│   ├── config.py
│   ├── fallbacks.py
│   ├── gemini_client.py
│   ├── llm_utils.py
│   ├── models.py
│   ├── pdf_generator.py
│   └── tools.py
├── requirements.txt
├── README.md
└── .env.example
```

## Notes

- The app is built for Malaysian IT procurement workflows.
- Local fallback behavior is intentional and helps keep the pipeline usable when external services are rate limited or unavailable.
- If you want, I can also add badges, screenshots, or a shorter executive summary section.
