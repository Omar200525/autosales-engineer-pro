# AutoSales Engineer Pro

AutoSales Engineer Pro is a Streamlit app for AI-assisted IT sales engineering. It turns a client brief or uploaded image into a structured procurement brief, builds a catalog-backed solution, reviews the result, and exports a quote-ready report.

Built for the APU AI Marathon 2026 Track 1 challenge.

## What It Does

- Converts text or image briefs into structured IT requirements.
- Builds a proposed bill of materials from a local SQLite catalog.
- Uses agent reasoning, self-critique, and reviewer checks to improve quality.
- Falls back to local deterministic logic when cloud providers fail or rate-limit.
- Generates a Streamlit solution report and PDF quote.
- Supports Malaysian IT procurement details such as MYR pricing, delivery regions, shipping, and SST.

## Agent Pipeline

```text
Client Text / Image
        |
        v
Visual Analyst -> Parser -> Sales Engineer -> Reviewer
   Gemini        Groq      Chutes/Groq/Local  Chutes/Groq/Local
        |
        v
Streamlit report + PDF quote
```

The live pipeline monitor shows each major step so judges and users can see why a solution was selected.

## Tech Stack

- Python 3.10+
- Streamlit
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

Fill in `.env`, then run:

```bash
streamlit run main.py
```

Open the app at:

```text
http://localhost:8501
```

## Environment Variables

Minimum recommended keys:

| Variable | Required | Purpose |
|---|---:|---|
| `GROQ_API_KEY` | Yes | Parser and fallback model calls |
| `CHUTES_API_KEY` | Yes | Sales Engineer and Reviewer primary model calls |
| `GEMINI_API_KEY` | Optional | Image brief analysis |
| `TAVILY_API_KEY` | Optional | Live web product search |

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
| Missing Groq key | Add `GROQ_API_KEY` to `.env`, then restart Streamlit |
| Missing Chutes key | Add `CHUTES_API_KEY` to `.env`, then restart Streamlit |
| Image upload does not analyze | Add `GEMINI_API_KEY` |
| Web search returns no results | Normal; the local catalog fallback still works |
| `catalog.db locked` | Stop Streamlit, delete `catalog.db`, restart |
| UI still shows old styling | Hard refresh the browser with `Ctrl+F5` |

## Notes

- Do not commit `.env`; it contains private API keys.
- Use `.env.example` as the public template.
- The app loads `.env` from the app directory even if Streamlit is launched from a parent folder.
