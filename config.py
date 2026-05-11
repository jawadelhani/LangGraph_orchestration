"""Env and app settings."""
import os

from dotenv import load_dotenv

load_dotenv()

# --- Database ---
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/pm_agents",
)

# --- LLM provider: groq | gemini | auto ---
# auto = use Groq if GROQ_API_KEY is set, else Gemini if GEMINI_API_KEY is set
_LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto").strip().lower()

GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_BASE_URL: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# LLM_MODE: live | dry_run | auto (auto = dry_run if no LLM API key, else live)
_LLM_MODE = os.getenv("LLM_MODE", "auto").strip().lower()


def _resolved_provider() -> str:
    if _LLM_PROVIDER in ("groq", "gemini"):
        return _LLM_PROVIDER
    # auto
    if GROQ_API_KEY:
        return "groq"
    if GEMINI_API_KEY:
        return "gemini"
    return "none"


def has_llm_credentials() -> bool:
    return _resolved_provider() != "none"


def active_llm_provider() -> str:
    """groq | gemini | none"""
    return _resolved_provider()


def is_llm_dry_run() -> bool:
    if _LLM_MODE == "dry_run":
        return True
    if _LLM_MODE == "live":
        return False
    return not has_llm_credentials()
