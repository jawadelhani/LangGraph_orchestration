"""Env and app settings."""
import os

from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
# gemini-2.0-flash often has stricter free-tier limits; 1.5-flash is a safer default.
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
# postgresql+psycopg2://user:pass@host:5432/dbname
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/pm_agents",
)

# LLM_MODE: live | dry_run | auto (auto = dry_run if no API key, else live)
_LLM_MODE = os.getenv("LLM_MODE", "auto").strip().lower()


def is_llm_dry_run() -> bool:
    if _LLM_MODE == "dry_run":
        return True
    if _LLM_MODE == "live":
        return False
    return not bool(GEMINI_API_KEY)
