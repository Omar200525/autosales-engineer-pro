# AutoSales Engineer Pro

AutoSales Engineer Pro is an AI-assisted presales engineering toolkit for turning client briefs into quote-ready IT solution proposals. It can parse text and image briefs, assemble catalog-backed bills of materials, review solution quality, export PDFs, and optionally send Telegram notifications.

## Highlights

- Text and image brief intake with structured requirement extraction.
- Catalog-backed solution planning with pricing, logistics, and compatibility checks.
- FastAPI backend with asynchronous pipeline runs and server-sent progress events.
- React frontend for running quotes, reviewing outputs, and browsing results.
- Streamlit demo UI for quick local experimentation.
- Deterministic local fallback paths when optional providers are unavailable.
- PDF proposal export and optional Telegram delivery.

## Quick Start

```bash
git clone https://github.com/Omar200525/autosales-engineer-pro.git
cd autosales-engineer-pro
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and add the provider keys you plan to use.

## Configuration

Minimum recommended keys:

| Variable | Required | Purpose |
|---|---:|---|
| `GROQ_API_KEY` | Yes | Parser and fallback model calls |
| `CHUTES_API_KEY` | Yes | Sales Engineer and Reviewer primary model calls |
| `GEMINI_API_KEY` | Optional | Image brief analysis |
| `TAVILY_API_KEY` | Optional | Live web product search |
| `API_CORS_ORIGINS` | Optional | Allowed React frontend origins for FastAPI |

Optional model and provider overrides are documented in `.env.example`.

## Run The App

Streamlit demo:

```bash
streamlit run main.py
```

FastAPI backend:

```bash
uvicorn backend.app:app --reload --port 8000
```

React frontend:

```bash
cd frontend
npm install
npm run dev
```

Open the frontend at `http://localhost:5173`. The backend health check is available at `http://localhost:8000/health`.

## Telegram Notifications

Telegram support is optional. It can send completion or failure notifications, attach generated PDFs, and run a local long-polling command bot while the FastAPI backend is running.

Add these values to `.env` to enable it:

```env
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_or_channel_id
TELEGRAM_INCLUDE_PDF=true
TELEGRAM_BOT_POLLING_ENABLED=true
```

Supported bot commands:

```text
/start - connect this chat and subscribe to live quote progress
/help - show commands
/status - show the latest run
/status <run_id> - show a specific run
/quote <brief> - start a quote from this chat
/subscribe - receive live run progress in this chat
/unsubscribe - stop live progress in this chat
```

Telegram failures are non-blocking. A quote run can still complete if the token, chat ID, or network request fails.

## Pipeline Flow

1. Parse the client brief.
2. Analyze any uploaded image brief.
3. Build a proposed solution and bill of materials.
4. Check budget, compatibility, delivery, and catalog/product sources.
5. Run self-critique and reviewer QA.
6. Generate a quote-ready solution report and PDF.

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
|   |-- gemini_client.py
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

## Tests

```bash
pytest
python -m compileall agents backend core main.py pipeline.py tests
```

For the frontend:

```bash
cd frontend
npm run build
```

## Troubleshooting

| Problem | Fix |
|---|---|
| Missing Groq key | Add `GROQ_API_KEY` to `.env`, then restart the app |
| Missing Chutes key | Add `CHUTES_API_KEY` to `.env`, then restart the app |
| React app cannot reach backend | Start `uvicorn backend.app:app --reload --port 8000` and check `API_CORS_ORIGINS` |
| Image upload does not analyze | Add `GEMINI_API_KEY` |
| Web search returns no results | The local catalog fallback still works |
| `catalog.db locked` | Stop running servers, delete `catalog.db`, then restart |
| UI still shows old styling | Hard refresh the browser with `Ctrl+F5` |

## Notes

- Do not commit `.env`; it contains private credentials.
- Use `.env.example` as the public configuration template.
- `catalog.db` is created and seeded automatically when the local catalog is first used.
- The app loads `.env` from the app directory even if launched from a parent folder.
