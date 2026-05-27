# AutoSales Engineer Pro

AutoSales Engineer Pro is an AI-assisted IT sales engineering platform. It turns a client brief or uploaded image into structured procurement requirements, builds a catalog-backed solution, reviews the result, and exports a quote-ready report.

Built for the APU AI Marathon 2026 Track 1 challenge: **The Autonomous Sales Engineer**.

## What It Does

- Converts text or image briefs into structured IT requirements.
- Uses LLM-backed agents to refine requirements, select a compatible solution, and review proposal quality.
- Builds a proposed bill of materials from a local SQLite catalog with real product URLs and MYR pricing.
- Uses deterministic guardrails for budget math, delivery, compatibility, shipping, SST, and fallback resilience.
- Produces quote-review evidence such as requirement coverage, supplier source proof, and agentic trace summaries without cluttering the client-facing proposal.
- Falls back to local deterministic logic when cloud providers fail or rate-limit.
- Generates an interactive React/FastAPI solution report, PDF quote, and optional Telegram updates.
- Supports Malaysian IT procurement details such as MYR pricing, delivery regions, shipping, and SST.

## AI Marathon Alignment

The system is aligned to the guide book's Track 1 requirements:

- **LLM & Agentic usage:** Groq refines requirements, Chutes performs bounded AI quote planning over catalog evidence, and the reviewer uses AI QA grounded by deterministic validation.
- **Constraint-based discovery:** the Sales Engineer searches catalog categories, rejects invalid product IDs, checks budget limits, preserves requirement coverage, and validates compatibility.
- **Logistics & fulfillment reasoning:** delivery region checks, estimated shipping fees, SST, delivery timeline, and total cost of ownership are included in the final report.
- **Dynamic quote generation:** output includes itemized products, supplier URLs, bill of materials, reasoning summary, recommendations, PDF export, and Telegram delivery.
- **Technical implementation:** AI outputs are validated against the local catalog so the prototype is demonstrable, reliable, and resistant to hallucinated prices or products.
- **Submission support:** the repository includes separate Gemini-ready Markdown prompts for the pitch deck and documentation PDF, while the app UI stays focused on quote review.

## Agent Pipeline

```text
Client Text / Image
        |
        v
Visual Analyst -> Parser -> Sales Engineer -> Reviewer
   Gemini        Groq      Chutes + tools     Chutes/Groq/Local
        |
        v
React/FastAPI report + PDF quote + Telegram updates
```

The live pipeline monitor shows each major step so judges and users can see why a solution was selected.

## Tech Stack

- Python 3.10+
- FastAPI
- React + Vite + TypeScript
- Streamlit legacy UI
- OpenAI-compatible clients
- Groq
- Chutes AI
- Google Gemini
- Pydantic
- SQLite
- ReportLab
- Tavily Search

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

Install Python dependencies:

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

Fill in `.env`, then start the FastAPI backend:

```bash
uvicorn backend.app:app --reload --port 8000
```

In another terminal, start the React frontend:

```bash
cd frontend
npm install
npm run dev
```

Open the app at:

```text
http://localhost:5173
```

The React app calls the FastAPI backend for catalog data, pipeline run creation,
live pipeline events, and PDF export. The backend keeps using the existing agent
pipeline in `pipeline.py`.

## Streamlit Legacy UI

The original Streamlit UI is still available as a fallback/demo path:

```bash
streamlit run main.py
```

Open the app at:

```text
http://localhost:8501
```

## Telegram Notifications

The FastAPI backend can automatically send a Telegram message when a pipeline
run completes or fails. Successful runs include a concise quote summary and, by
default, the generated quote PDF. The bot can also respond to commands and show
live quote progress while the FastAPI backend is running.

1. Create a bot with Telegram BotFather and copy the bot token.
2. Add the bot to the target chat or channel.
3. Find the target chat ID. Channel and group IDs can be negative; keep the
        value as text in `.env`.
4. Set these values in `.env`, then restart the FastAPI backend:

```env
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_or_channel_id
TELEGRAM_INCLUDE_PDF=true
TELEGRAM_BOT_POLLING_ENABLED=true
```

Telegram notification failures are non-blocking. A quote run can still complete
even if Telegram rejects the token, the chat ID is wrong, or the network is
temporarily unavailable.

Supported Telegram commands:

```text
/start - connect this chat and subscribe to live quote progress
/help - show commands
/status - show the latest run
/status <run_id> - show a specific run
/quote <brief> - start a quote from this chat
/subscribe - receive live run progress in this chat
/unsubscribe - stop live progress in this chat
```

You can also paste a full procurement brief directly into the chat. If it looks
like a brief with fields such as `Client:`, `Use case:`, `Budget:`, and
`Delivery location:`, the bot starts a pipeline run automatically.

## Environment Variables

Minimum recommended keys:

| Variable | Required | Purpose |
|---|---:|---|
| `GROQ_API_KEY` | Yes | Parser and fallback model calls |
| `CHUTES_API_KEY` | Yes | Sales Engineer and Reviewer primary model calls |
| `GEMINI_API_KEY` | Optional | Image brief analysis |
| `TAVILY_API_KEY` | Optional | Live web product search |
| `API_CORS_ORIGINS` | Optional | Allowed React frontend origins for FastAPI |
| `TELEGRAM_ENABLED` | Optional | Enables automatic Telegram completion/failure notifications |
| `TELEGRAM_BOT_TOKEN` | Optional | Telegram bot token, required only when Telegram is enabled |
| `TELEGRAM_CHAT_ID` | Optional | Fixed Telegram chat/channel destination, required only when enabled |
| `TELEGRAM_INCLUDE_PDF` | Optional | Attach generated quote PDFs to successful Telegram notifications |
| `TELEGRAM_BOT_POLLING_ENABLED` | Optional | Enables local long-polling command bot and live progress updates |
| `TELEGRAM_POLLING_TIMEOUT_SECONDS` | Optional | Telegram `getUpdates` long-poll timeout |
| `TELEGRAM_TIMEOUT_SECONDS` | Optional | Telegram Bot API request timeout |

Optional model/base URL overrides:

| Variable | Default |
|---|---|
| `GROQ_BASE_URL` | `https://api.groq.com/openai/v1` |
| `GROQ_PARSER_MODEL` | `llama-3.3-70b-versatile` |
| `GROQ_FALLBACK_MODEL` | `llama-3.1-8b-instant` |
| `CHUTES_BASE_URL` | `https://llm.chutes.ai/v1` |
| `ORCHESTRATOR_MODEL` | `Qwen/Qwen3.6-27B-TEE` |
| `REVIEWER_MODEL` | `deepseek-ai/DeepSeek-V3.2-TEE` |
| `GEMINI_VISION_MODEL` | `gemini-2.5-flash` |
| `GEMINI_FALLBACK_VISION_MODEL` | `gemini-2.0-flash` |

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

## Submission Checklist

- Run the FastAPI backend and React frontend before judging.
- Confirm `.env` contains `GROQ_API_KEY` and `CHUTES_API_KEY`.
- Add `GEMINI_API_KEY` if image brief analysis will be demonstrated.
- Keep `.env` private; use `.env.example` for public configuration.
- Use the generated PDF export as the quote-ready deliverable.

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
|   |-- run_store.py
|   |-- schemas.py
|   |-- telegram_bot.py
|   `-- telegram_notifications.py
|-- core/
|   |-- catalog.py
|   |-- config.py
|   |-- fallbacks.py
|   |-- llm_utils.py
|   |-- models.py
|   |-- pdf_generator.py
|   |-- telegram_client.py
|   |-- telegram_config.py
|   `-- tools.py
|-- frontend/
|   |-- package.json
|   |-- vite.config.ts
|   `-- src/
|       |-- App.tsx
|       |-- api.ts
|       |-- main.tsx
|       |-- styles.css
|       `-- types.ts
`-- tests/
    |-- test_backend_api.py
    |-- test_sales_engineer_fast_planner.py
    `-- test_telegram_notifications.py
```

## Troubleshooting

| Problem | Fix |
|---|---|
| Missing Groq key | Add `GROQ_API_KEY` to `.env`, then restart the backend |
| Missing Chutes key | Add `CHUTES_API_KEY` to `.env`, then restart the backend |
| React app cannot reach backend | Start `uvicorn backend.app:app --reload --port 8000` and check `API_CORS_ORIGINS` |
| Image upload does not analyze | Add `GEMINI_API_KEY` |
| Web search returns no results | Normal; the local catalog fallback still works |
| `catalog.db locked` | Stop Streamlit, delete `catalog.db`, restart |
| UI still shows old styling | Hard refresh the browser with `Ctrl+F5` |

## Notes

- Do not commit `.env`; it contains private API keys.
- Use `.env.example` as the public template.
- The app loads `.env` from the app directory even if Streamlit is launched from a parent folder.
