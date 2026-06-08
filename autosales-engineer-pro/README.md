# AutoSales Engineer Pro

AutoSales Engineer Pro is a Vite + React frontend with a FastAPI backend for AI-assisted IT sales engineering. It turns a client brief or uploaded image into a structured procurement brief, builds a catalog-backed solution, reviews the result, and exports a quote-ready report.

## What It Does

- Converts text or image briefs into structured IT requirements.
- Builds a proposed bill of materials from a local SQLite catalog.
- Uses multi-agent reasoning, self-critique, and reviewer checks to improve quality.
- Falls back to local deterministic logic when cloud providers fail or rate-limit.
- Generates a React frontend report and PDF quote from the backend.
- Supports Malaysian IT procurement details such as MYR pricing, delivery regions, shipping, and SST.
- Streams live pipeline updates through the API and frontend.
- Can be driven from Telegram for quote creation and progress tracking.

## Agent Pipeline

```text
Client Text / Image
        |
        v
Visual Analyst -> Parser -> Sales Engineer -> Reviewer
   Gemini        Groq      Chutes/Groq/Local  Chutes/Groq/Local
        |
        v
FastAPI backend + React (Vite) frontend report + PDF quote
```

The live pipeline monitor shows each major step so users can see why a solution was selected.

## Key Features

- Image-to-brief extraction for whiteboards, RFQs, diagrams, and server-room photos.
- Structured procurement parsing for Malaysian IT sales workflows.
- Tool-assisted solution generation with catalog search, compatibility checks, budget fit, delivery validation, and alternatives.
- Self-critique and reviewer feedback loops for higher-quality outputs.
- Local SQLite catalog fallback for resilient offline or provider-limited operation.
- Optional web product search when `TAVILY_API_KEY` is available.
- Professional quote export with line items, totals, reasoning, and delivery estimates.
- React dashboard with a live pipeline monitor.
- FastAPI backend with SSE progress events.
- Telegram bot support for live progress, quote creation, and run status.

## Tech Stack

- Python 3.10+
- FastAPI backend (uvicorn)
- React frontend (Vite)
- OpenAI-compatible clients
- Groq
- Chutes AI
- Google Gemini
- Pydantic
- SQLite
- ReportLab
- Tavily Search
- Telegram Bot API

## Quick Start

Clone the repository:

```bash
git clone https://github.com/Omar200525/autosales-engineer-pro.git
cd autosales-engineer-pro
```

Create and activate a virtual environment.

Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create your environment file:

```bash
copy .env.example .env
```

On macOS/Linux:

```bash
cp .env.example .env
```

Fill in `.env`, then run the backend and frontend:

Start the backend:

```bash
c:/Hackathon/.venv/Scripts/python.exe -m uvicorn backend.app:app --reload --port 8000
```

Start the frontend:

```bash
cd frontend
npm install
npm run dev -- --host
```

Open the UI at `http://localhost:5173`.

## Environment Variables

Minimum recommended keys:

| Variable | Required | Purpose |
|---|---:|---|
| `GROQ_API_KEY` | Yes | Parser and fallback model calls |
| `CHUTES_API_KEY` | Yes | Sales Engineer and Reviewer primary model calls |
| `GEMINI_API_KEY` | Optional | Image brief analysis |
| `TAVILY_API_KEY` | Optional | Live web product search |

Telegram bot settings:

| Variable | Default | Purpose |
|---|---|---|
| `TELEGRAM_ENABLED` | `false` | Enable Telegram notifications and bot commands |
| `TELEGRAM_BOT_TOKEN` | empty | Telegram bot token from BotFather |
| `TELEGRAM_CHAT_ID` | empty | Default chat to subscribe |
| `TELEGRAM_INCLUDE_PDF` | `true` | Send the generated PDF with completion messages |
| `TELEGRAM_BOT_POLLING_ENABLED` | `true` | Enable long-polling command bot |
| `TELEGRAM_POLLING_TIMEOUT_SECONDS` | `20` | Polling timeout |
| `TELEGRAM_TIMEOUT_SECONDS` | `12` | Telegram request timeout |
| `TELEGRAM_API_BASE_URL` | `https://api.telegram.org` | Telegram API endpoint |

Optional model/base URL overrides:

| Variable | Default |
|---|---|
| `GROQ_BASE_URL` | `https://api.groq.com/openai/v1` |
| `GROQ_PARSER_MODEL` | `llama-3.3-70b-versatile` |
| `GROQ_FALLBACK_MODEL` | `llama-3.1-8b-instant` |
| `CHUTES_BASE_URL` | `https://llm.chutes.ai/v1` |
| `ORCHESTRATOR_MODEL` | `Qwen/Qwen2.5-72B-Instruct` |
| `REVIEWER_MODEL` | `deepseek-ai/DeepSeek-R1` |
| `GEMINI_VISION_MODEL` | `gemini-3.5-flash` |
| `GEMINI_FALLBACK_VISION_MODEL` | `gemini-2.5-flash` |

## Telegram Bot

When Telegram is enabled, the backend can run a small long-polling command bot. It can subscribe a chat to live progress, send quote completion messages, and start quote runs directly from Telegram.

Commands:

- `/start` connects the chat and subscribes it to live quote progress.
- `/help` shows the available commands.
- `/status` shows the latest run.
- `/status <run_id>` shows a specific run.
- `/quote <brief>` starts a quote from the chat.
- `/subscribe` enables live progress for the chat.
- `/unsubscribe` stops live progress in the chat.

You can also paste a full client brief directly into the chat. If Telegram polling is enabled and the text looks like a brief, the bot can start a quote automatically.

## Why Generation Can Take Time

The app runs multiple steps in order:

1. Parse the brief.
2. Build a solution.
3. Search/check catalog products.
4. Run self-critique.
5. Run reviewer QA.
6. Optionally revise and review again.

Each cloud API call has a timeout and may fall back to another provider or local logic. The audit trail in the UI shows where time was spent.

## Local Fallback Behavior

The app is designed to remain usable during provider failures, rate limits, or tool-call issues.

- If cloud tool-calling fails, the Sales Engineer can select products from the local SQLite catalog.
- If review APIs fail, the Reviewer can perform a deterministic local QA pass.
- If Tavily search is unavailable, catalog search still works.
- `catalog.db` is created and seeded automatically on first run.

## Output

The generated quote package includes:

- Client summary
- Itemized bill of materials
- Quantity, unit price, subtotal, shipping, SST, and TCO
- Product URLs and source platforms
- Compatibility checks
- Delivery feasibility
- Reviewer technical and commercial scores
- PDF export

## Project Structure

```text
autosales-engineer-pro/
|-- main.py
|-- pipeline.py
|-- requirements.txt
|-- README.md
|-- .env.example
|-- agents/
|   |-- parser_agent.py
|   |-- reviewer_agent.py
|   |-- sales_engineer_agent.py
|   `-- visual_analyst_agent.py
|-- backend/
|   |-- app.py
|   |-- telegram_bot.py
|   |-- telegram_notifications.py
|   `-- run_store.py
`-- core/
    |-- catalog.py
    |-- config.py
    |-- fallbacks.py
    |-- llm_utils.py
    |-- models.py
    |-- pdf_generator.py
    `-- tools.py
```

## Troubleshooting

| Problem | Fix |
|---|---|
| Missing Groq key | Add `GROQ_API_KEY` to `.env`, then restart the backend |
| Missing Chutes key | Add `CHUTES_API_KEY` to `.env`, then restart the backend |
| Image upload does not analyze | Add `GEMINI_API_KEY` |
| Web search returns no results | Normal; the local catalog fallback still works |
| `catalog.db locked` | Stop the backend, delete `catalog.db`, restart |
| Telegram bot is not responding | Check `TELEGRAM_ENABLED`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and `TELEGRAM_BOT_POLLING_ENABLED` |

## Notes

- Do not commit `.env`; it contains private API keys.
- Use `.env.example` as the public template.
- The backend loads `.env` from the app directory so services can read configuration.
