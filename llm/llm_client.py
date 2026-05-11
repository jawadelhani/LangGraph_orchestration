"""Single entry for chat completions: Groq (default) or Gemini."""

from __future__ import annotations

from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GROQ_API_KEY,
    GROQ_BASE_URL,
    GROQ_MODEL,
    active_llm_provider,
    is_llm_dry_run,
)


class LLMQuotaError(RuntimeError):
    """429 / rate limit or quota exceeded from the active provider."""


def call_llm(prompt: str) -> str:
    """One-shot text generation used by supervisor and BaseAgent."""
    if is_llm_dry_run():
        raise RuntimeError("call_llm must not run in dry_run mode.")

    provider = active_llm_provider()
    if provider == "none":
        raise RuntimeError(
            "No LLM API key. Set GROQ_API_KEY (recommended) or GEMINI_API_KEY in .env, "
            "or use LLM_MODE=dry_run."
        )

    if provider == "groq":
        return _call_groq(prompt)
    return _call_gemini(prompt)


def _call_groq(prompt: str) -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set.")

    from openai import APIError, OpenAI, RateLimitError

    client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)
    try:
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
    except RateLimitError as e:
        raise LLMQuotaError(
            "Groq rate limit (429). Wait and retry or check "
            "https://console.groq.com/docs/rate-limits"
        ) from e
    except APIError as e:
        if getattr(e, "status_code", None) == 429:
            raise LLMQuotaError(str(e)) from e
        raise

    text = resp.choices[0].message.content
    return (text or "").strip()


def _call_gemini(prompt: str) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set.")

    import google.generativeai as genai
    from google.api_core.exceptions import ResourceExhausted

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)
    try:
        resp = model.generate_content(prompt)
    except ResourceExhausted as e:
        raise LLMQuotaError(
            "Gemini quota exceeded (429). Prefer Groq: set GROQ_API_KEY and LLM_PROVIDER=groq. "
            "https://ai.google.dev/gemini-api/docs/rate-limits"
        ) from e
    return (resp.text or "").strip()


# Backwards compatibility
def call_gemini(prompt: str) -> str:
    return call_llm(prompt)
