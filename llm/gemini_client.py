import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

from config import GEMINI_API_KEY, GEMINI_MODEL, is_llm_dry_run


class LLMQuotaError(RuntimeError):
    """Raised when the Gemini API returns 429 / quota exhausted."""


def configure() -> None:
    if not GEMINI_API_KEY:
        raise RuntimeError("Set GEMINI_API_KEY in .env or the environment.")
    genai.configure(api_key=GEMINI_API_KEY)


def call_gemini(prompt: str) -> str:
    if is_llm_dry_run():
        raise RuntimeError("call_gemini must not run in dry_run mode (use node-level stubs).")
    configure()
    model = genai.GenerativeModel(GEMINI_MODEL)
    try:
        resp = model.generate_content(prompt)
    except ResourceExhausted as e:
        raise LLMQuotaError(
            "Gemini quota exceeded (429). Set LLM_MODE=dry_run in .env to run the workflow "
            "without the API, or change GEMINI_MODEL / wait / check billing at "
            "https://ai.google.dev/gemini-api/docs/rate-limits"
        ) from e
    return (resp.text or "").strip()
