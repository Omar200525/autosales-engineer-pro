# AutoSales Engineer Pro

AutoSales Engineer Pro is an AI-assisted toolkit for authoring IT solutions and producing professional, quote-ready proposals. It combines requirement parsing, catalog-backed solution assembly, automated validation, and PDF export to streamline technical presales and presales engineering workflows.

## Highlights

- Parse text or image-based briefs into structured procurement requirements.
- Assemble a catalog-backed bill of materials with pricing and basic logistics.
- Automated reviewer checks and deterministic local fallbacks for reliability.
- Export polished PDF proposals and optionally deliver them via Telegram.

## Quick Start

Clone the repository and install dependencies:

```bash
git clone https://github.com/Omar200525/autosales-engineer-pro.git
cd autosales-engineer-pro
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
copy .env.example .env
```

## Configuration

Edit `.env` to provide API keys and model settings. The application supports optional integrations (search, vision, and alternative LLM providers) and falls back to deterministic local logic when integrations are not configured.

## Running (examples)

Streamlit demo UI:

```bash
streamlit run main.py
```

FastAPI backend + React frontend (example):

```bash
uvicorn backend.app:app --reload --port 8000
cd frontend
npm install
npm run dev
```

Open the frontend at `http://localhost:5173` when running the React app.

## Telegram Notifications

This project includes optional Telegram integration for pipeline notifications and PDF delivery. The backend contains helper modules for Telegram (`backend/telegram_notifications.py`, `core/telegram_client.py`) and example command handling.

Environment variables to enable Telegram features:

- `TELEGRAM_ENABLED=true` — enable automatic notifications
- `TELEGRAM_BOT_TOKEN` — bot token from BotFather
- `TELEGRAM_CHAT_ID` — chat or channel id to receive messages
- `TELEGRAM_INCLUDE_PDF=true` — attach generated PDF to successful notifications
- `TELEGRAM_BOT_POLLING_ENABLED=true` — enable local long-polling command bot
- `TELEGRAM_POLLING_TIMEOUT_SECONDS` — long-poll timeout for `getUpdates`
- `TELEGRAM_TIMEOUT_SECONDS` — HTTP request timeout when calling Bot API

Basic examples (Python) to send a text message or a PDF file via the Bot API:

```python
import requests

def send_telegram_message(token: str, chat_id: str, text: str):
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text})

def send_telegram_file(token: str, chat_id: str, file_path: str, caption: str = ""):
        url = f"https://api.telegram.org/bot{token}/sendDocument"
        with open(file_path, "rb") as f:
                requests.post(url, data={"chat_id": chat_id, "caption": caption}, files={"document": f})
```

The backend supports a set of chat commands for convenience (e.g. `/start`, `/status`, `/quote`) — consult `backend/telegram_notifications.py` for implementation details. Notification failures are non-blocking.

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

Common issues and fixes:

- Missing Groq key: add `GROQ_API_KEY` to `.env` and restart the backend.
- Missing Chutes key: add `CHUTES_API_KEY` to `.env` and restart the backend.
- Telegram not sending: verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` and ensure the bot is added to the chat.
- `catalog.db locked`: stop running servers, delete `catalog.db`, and restart.

## Contributing

Contributions are welcome. Please open an issue to discuss planned changes and follow the standard GitHub workflow: fork, feature branch, tests, and pull request.

## License & Contact

Add a `LICENSE` file to indicate project licensing. For questions or commercial enquiries, contact the repository maintainers.

--
If you'd like, I can also add a small helper in `core/tools.py` to send the final PDF automatically when a report is generated.
## Configuration

Edit `.env` to provide API keys and model settings. Minimal configuration varies by deployment; the project supports optional integrations (search, vision, and alternative LLM providers) and falls back to deterministic local logic when integrations are not configured.

## Telegram integration

This project can optionally send pipeline notifications and deliverable PDFs to a Telegram bot. To enable Telegram notifications, add the following variables to your `.env`:

- `TELEGRAM_BOT_TOKEN` — your bot token from BotFather
- `TELEGRAM_CHAT_ID` — the numeric chat id (or channel id) to receive messages

Example usage (Python):

```python
import requests

def send_telegram_message(token: str, chat_id: str, text: str):
	url = f"https://api.telegram.org/bot{token}/sendMessage"
	requests.post(url, json={"chat_id": chat_id, "text": text})

def send_telegram_file(token: str, chat_id: str, file_path: str, caption: str = ""):
	url = f"https://api.telegram.org/bot{token}/sendDocument"
	with open(file_path, "rb") as f:
		requests.post(url, data={"chat_id": chat_id, "caption": caption}, files={"document": f})
```

If you want, I can add a small helper in `core/tools.py` to send the final PDF automatically when a report is generated.

## Usage

Run the application (Streamlit example):
>>>>>>> 7c75973 (docs: add Telegram integration section to READMEs)

```bash
streamlit run main.py
```

<<<<<<< HEAD
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
=======
Workflow:

1. Provide a client brief via text or image upload.
2. Run the pipeline to generate a proposed solution and quote.
3. Review and export the final PDF proposal.

## Project Structure

- `main.py` — application entry point (example Streamlit UI)
- `pipeline.py` — orchestration of parsing, solution building, and review
- `agents/` — modular agents for parsing, visual analysis, solution construction, and review
- `core/` — core utilities, catalog, models, and PDF generation

## Contributing

Contributions are welcome. Please open an issue to discuss planned changes and follow typical GitHub workflow: fork, feature branch, tests, and pull request.

## License & Contact

Specify your preferred open-source license in `LICENSE`. For questions or commercial enquiries, contact the maintainers via the project repository.

--
This README was revised to present the project as a professional engineering toolkit. If you prefer a shorter executive summary, badges, or screenshots, tell me which and I'll add them.
>>>>>>> 7c75973 (docs: add Telegram integration section to READMEs)
