"""Configuration and client factories for AutoSales Engineer Pro."""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_VISION_MODEL = os.getenv("GEMINI_VISION_MODEL", "gemini-3.5-flash")
GEMINI_FALLBACK_VISION_MODEL = os.getenv("GEMINI_FALLBACK_VISION_MODEL", "gemini-2.5-flash")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_PARSER_MODEL = os.getenv("GROQ_PARSER_MODEL", "llama-3.3-70b-versatile")
GROQ_FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant")

CHUTES_API_KEY = os.getenv("CHUTES_API_KEY", "")
CHUTES_BASE_URL = os.getenv("CHUTES_BASE_URL", "https://llm.chutes.ai/v1")
ORCHESTRATOR_MODEL = os.getenv("ORCHESTRATOR_MODEL", "Qwen/Qwen2.5-72B-Instruct")
REVIEWER_MODEL = os.getenv("REVIEWER_MODEL", "deepseek-ai/DeepSeek-R1")

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")


def _missing_key_message(provider: str, env_name: str) -> str:
    return (
        f"Missing {provider} API key. Add {env_name}=your_key_here to .env, "
        "then restart Streamlit. See .env.example for the full setup."
    )


@lru_cache(maxsize=1)
def get_chutes_client() -> OpenAI:
    """Return an OpenAI-compatible Chutes AI client."""
    if not CHUTES_API_KEY:
        raise RuntimeError(_missing_key_message("Chutes AI", "CHUTES_API_KEY"))
    return OpenAI(base_url=CHUTES_BASE_URL, api_key=CHUTES_API_KEY)


@lru_cache(maxsize=1)
def get_groq_client() -> OpenAI:
    """Return an OpenAI-compatible Groq client."""
    if not GROQ_API_KEY:
        raise RuntimeError(_missing_key_message("Groq", "GROQ_API_KEY"))
    return OpenAI(base_url=GROQ_BASE_URL, api_key=GROQ_API_KEY)


@lru_cache(maxsize=1)
def get_gemini_client():
    """Return a Gemini API client."""
    if not GEMINI_API_KEY:
        raise RuntimeError(_missing_key_message("Gemini", "GEMINI_API_KEY"))
    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError("Missing google-genai. Run: pip install -r requirements.txt") from exc
    return genai.Client(api_key=GEMINI_API_KEY)
