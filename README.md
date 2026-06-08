# AutoSales Engineer Pro

AutoSales Engineer Pro is a Vite + React frontend with a FastAPI backend for AI-assisted IT sales engineering. It converts client briefs or uploaded images into structured procurement requests, builds a catalog-backed solution, reviews it with multiple agents, and exports a quote-ready report with reasoning and delivery details.

## Overview

The system runs a four-agent pipeline:

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
        FastAPI backend + React (Vite) frontend report + PDF quote
```

Each stage adds structure and validation:

- The Visual Analyst extracts text and context from uploaded images.
- The Parser turns the raw brief into a structured procurement request.
- The Sales Engineer builds a compatible solution from the local catalog and helper tools.
- The Reviewer checks technical quality, commercial fit, and delivery feasibility.

## Key Features

- Text and image brief intake for sales discovery, RFQs, whiteboards, diagrams, and server-room photos.
- Structured procurement parsing for Malaysian IT workflows.
- Tool-assisted solution generation with catalog search, compatibility checks, budget fit, delivery validation, and alternatives.
- Multi-agent reasoning with self-critique and reviewer QA.
- Local SQLite catalog fallback when cloud providers are unavailable or rate limited.
- Optional live web product search when `TAVILY_API_KEY` is configured.
- PDF quote generation with line items, totals, delivery details, and reviewer feedback.
- React/Vite frontend for a modern quote and pipeline experience.
- FastAPI backend with SSE-based live pipeline updates.
- Optional Telegram bot for live progress, status checks, and quote creation.

## Technology Stack

- Python 3.10+
- FastAPI backend (uvicorn)
- React frontend (Vite)
- OpenAI-compatible provider clients
- Pydantic
- SQLite
- ReportLab
- Tavily search integration
- Telegram Bot API integration

## Requirements

- Python 3.10 or later
- Node.js for the Vite frontend
- API keys for the providers you want to use
- Optional Telegram bot token and chat ID for bot-based runs and notifications

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate    # Windows
# or: source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
copy .env.example .env     # Windows
# or: cp .env.example .env  # macOS/Linux
cd frontend
npm install
```

Update `.env` with your provider keys and optional Telegram settings.

## Environment Variables

Core model/provider settings:

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

Telegram bot settings:

```text
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=123456:abc...
TELEGRAM_CHAT_ID=123456789
TELEGRAM_INCLUDE_PDF=true
TELEGRAM_BOT_POLLING_ENABLED=true
TELEGRAM_POLLING_TIMEOUT_SECONDS=20
TELEGRAM_TIMEOUT_SECONDS=12
TELEGRAM_API_BASE_URL=https://api.telegram.org
```

## Run

Start the backend:

```bash
c:/Hackathon/.venv/Scripts/python.exe -m uvicorn backend.app:app --reload --port 8000
```

Start the frontend:

```bash
cd frontend
npm run dev -- --host
```

Open the UI at `http://localhost:5173` and the API at `http://127.0.0.1:8000`.

## Telegram Bot

When Telegram is enabled, the backend starts a small long-polling bot that can subscribe a chat to live run progress and start quote runs directly from Telegram.

Commands:

- `/start` connects the chat and subscribes it to live quote progress.
- `/help` shows the available commands.
- `/status` shows the latest run.
- `/status <run_id>` shows a specific run.
- `/quote <brief>` starts a quote from the chat.
- `/subscribe` enables live progress for the chat.
- `/unsubscribe` stops live progress in the chat.

You can also paste a full client brief directly into the chat. If Telegram polling is enabled and the text looks like a brief, the bot can start a quote automatically.

## How To Use

1. Open the React frontend.
2. Enter a text brief or upload an image.
3. Launch the agent pipeline.
4. Review the generated quote, reasoning, and PDF output.
5. Optionally use the Telegram bot to start a run or track progress.

## Example Brief

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

## Pipeline Behavior

The pipeline is designed to stay resilient when provider limits or tool failures occur:

- The Sales Engineer can fall back to a deterministic local catalog builder.
- Groq prompts are compacted to reduce request-size and TPM issues.
- The Reviewer can use a fallback path if the primary provider is unavailable.
- The UI shows a live pipeline monitor so you can see which agent is active.

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
├── backend/
│   ├── app.py
│   ├── telegram_bot.py
│   ├── telegram_notifications.py
│   └── run_store.py
├── core/
│   ├── catalog.py
│   ├── config.py
│   ├── fallbacks.py
│   ├── gemini_client.py
│   ├── llm_utils.py
│   ├── models.py
│   ├── pdf_generator.py
│   └── tools.py
├── frontend/
├── requirements.txt
├── README.md
└── .env.example
```

## Notes

- Do not commit `.env`; it contains private API keys.
- Use `.env.example` as the public template.
- The backend loads `.env` from the app directory so tools and services can read configuration.
