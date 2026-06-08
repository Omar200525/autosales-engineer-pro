# AutoSales Engineer Pro

AutoSales Engineer Pro is a Vite + React frontend with a FastAPI backend for AI-assisted IT sales engineering. It turns a client brief or image into a structured solution, validates the result through multiple agents, and produces a quote-ready report with supporting rationale.

## Overview

The application runs a four-agent pipeline:

```
Client Text / Image
    |
    v
Visual Analyst  ->  Parser  ->  Sales Engineer  ->  Reviewer
(Gemini)            (Groq)      (Chutes / Groq)     (Chutes / Groq)
    |                |              |                 |
    +----------------+--------------+-----------------+
                 |
                 v
        FastAPI backend + React (Vite) frontend report + PDF quote
```

Each stage adds structure and validation:

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
- Clean React dashboard with a live pipeline monitor.

## Technology Stack

- Python 3.10+
- FastAPI backend (uvicorn)
- React frontend (Vite)
- OpenAI-compatible provider clients
- Pydantic
- Rich
- ReportLab
- SQLite
- Tavily search integration

## Requirements

You will need:

- Python 3.10 or later
- API keys for the providers you want to use
- A virtual environment for local development

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate    # Windows
# or: source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
copy .env.example .env     # Windows
# or: cp .env.example .env  # macOS/Linux
```

Update `.env` with your provider keys and preferred models:

```text
GEMINI_API_KEY=your_gemini_key
GEMINI_VISION_MODEL=gemini-3.5-flash
GEMINI_FALLBACK_VISION_MODEL=gemini-2.5-flash
GROQ_API_KEY=your_groq_key
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_PARSER_MODEL=llama-3.3-70b-versatile
GROQ_FALLBACK_MODEL=llama-3.1-8b-instant
CHUTES_API_KEY=your_chutes_key
CHUTES_BASE_URL=https://llm.chutes.ai/v1
ORCHESTRATOR_MODEL=Qwen/Qwen2.5-72B-Instruct
REVIEWER_MODEL=deepseek-ai/DeepSeek-R1
TAVILY_API_KEY=tvly_your_key_here
```

## Run (development)

Start the backend (FastAPI):

```bash
c:/Hackathon/.venv/Scripts/python.exe -m uvicorn backend.app:app --reload --port 8000
```

Start the frontend (Vite):

```bash
cd frontend
npm install
npm run dev -- --host
```

Open the UI at `http://localhost:5173` and the API at `http://127.0.0.1:8000`.

The application creates `catalog.db` on backend startup. That file is intentionally gitignored. If Tavily is not configured or unavailable, the backend continues with the local SQLite catalog.

## How To Use

1. Open the app in the React frontend.
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
