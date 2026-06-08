"""Env and app settings."""
import os

from dotenv import load_dotenv

load_dotenv()

# --- Database ---
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/pm_agents",
)

# --- LLM provider: Groq ---
GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_BASE_URL: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

# LLM_MODE: live | dry_run | auto (auto = dry_run if no LLM API key, else live)
_LLM_MODE = os.getenv("LLM_MODE", "auto").strip().lower()


def has_llm_credentials() -> bool:
    return bool(GROQ_API_KEY)


def is_llm_dry_run() -> bool:
    if _LLM_MODE == "dry_run":
        return True
    if _LLM_MODE == "live":
        return False
    return not has_llm_credentials()
