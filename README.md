# AutoSales Engineer Pro

AutoSales Engineer Pro is a Python Streamlit application for AI-assisted technical sales consulting. It runs a four-agent pipeline across three AI providers:

```text
                           +----------------------+
                           | Client Text / Image  |
                           +----------+-----------+
                                      |
             +------------------------+------------------------+
             |                                                 |
             v                                                 v
+---------------------------+                     +---------------------------+
| Agent 0: Visual Analyst   |                     | Agent 1: Parser Agent    |
| Provider: Google Gemini   |                     | Provider: Groq           |
| Model: Gemini 3.5 Flash   |---- extracted ----->| Model: Llama 3.3 70B     |
+-------------+-------------+                     +-------------+-------------+
                                                            |
                                                            v
                                              +-----------------------------+
                                              | Agent 2: Sales Engineer    |
                                              | Provider: Chutes AI        |
| Model: Qwen 2.5 72B        |
| Fallback: Groq             |
                                              | Tools: catalog, web, quote |
                                              +--------------+--------------+
                                                             |
                                                             v
                                              +-----------------------------+
                                              | Agent 3: Senior Reviewer   |
                                              | Provider: Chutes AI        |
| Model: DeepSeek-R1         |
| Fallback: Groq             |
                                              +--------------+--------------+
                                                             |
                                                             v
                                              +-----------------------------+
                                              | Streamlit Report + PDF     |
                                              +-----------------------------+
```

## Features

- Vision-based extraction from whiteboards, scanned RFQs, diagrams, and server-room photos.
- Groq-hosted Llama parser for Malaysian IT procurement requirements.
- Qwen 2.5 72B sales engineer with OpenAI function-calling tools.
- DeepSeek-R1 senior review pass with technical and commercial scoring.
- Self-critique loop with up to three improvement iterations.
- SQLite fallback catalog with exactly 40 seeded products across 8 categories.
- Tavily-powered real web product search when `TAVILY_API_KEY` is present.
- Itemized bill of materials, product URLs, source platforms, shipping estimates, SST, TCO, reasoning summary, and delivery timeline.
- Professional ReportLab PDF quote generation.

## Tech Stack

- Python 3.10+
- Streamlit >= 1.35.0
- OpenAI Python SDK >= 1.30.0
- Pydantic >= 2.0.0
- python-dotenv >= 1.0.0
- Rich >= 13.0.0
- ReportLab >= 4.0.0
- tavily-python >= 0.3.0
- SQLite

## Setup

```bash
cd autosales-engineer-pro
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Fill in `.env`:

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

Run:

```bash
streamlit run main.py
```

`catalog.db` is created on startup and is intentionally gitignored. If Tavily is not configured or unavailable, the app logs a warning and continues with the SQLite catalog.

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

Upload any of these in the **Image Upload** or **Both** modes:

- A whiteboard photo listing budget, users, office location, and device needs.
- A scanned RFQ document with procurement requirements.
- A hand-drawn network diagram with router, switch, AP, firewall, and NAS labels.
- A photo of an existing server room or network rack.

## Self-Critique And Review

The Sales Engineer agent first builds a complete solution using catalog, compatibility, budget, delivery, alternative, and web-search tools. It then critiques its own answer for category coverage, budget fit, user quantities, compatibility, and value swaps. If the critique fails, it revises and tries again, up to three self-critique passes.

After that, the Reviewer agent independently evaluates technical soundness, commercial value, risk, scalability, and vendor diversity. If the reviewer rejects the solution, the pipeline performs one revision pass and sends the revised solution back to DeepSeek-R1.

## Quote Output

Both the Streamlit report and generated PDF include:

1. **Itemized Bill of Materials**: product name, quantity, unit price, product URL, source platform, and subtotal.
2. **Logistics & Cost of Ownership**: estimated shipping fee, Malaysian SST, TCO per product, and grand total TCO.
3. **Reasoning Summary**: a 150-200 word rationale generated by the Sales Engineer.
4. **Delivery Timeline Estimate**: West Malaysia 2-5 business days, East Malaysia 5-10 business days, or Nationwide 3-7 business days.

## Project Structure

```text
autosales-engineer-pro/
├── main.py
├── agents/
│   ├── __init__.py
│   ├── visual_analyst_agent.py
│   ├── parser_agent.py
│   ├── sales_engineer_agent.py
│   └── reviewer_agent.py
├── core/
│   ├── __init__.py
│   ├── catalog.py
│   ├── tools.py
│   ├── models.py
│   ├── config.py
│   ├── llm_utils.py
│   └── pdf_generator.py
├── pipeline.py
├── .env
├── .env.example
├── requirements.txt
└── README.md
```
