"""Env and app settings."""
import os

from dotenv import load_dotenv

load_dotenv()

# --- Database ---
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/pm_agents",
)

# --- LLM Provider Selection ---
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "auto").strip().lower()

# --- Groq Configuration ---
GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_BASE_URL: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

# --- Ollama Configuration ---
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.1")

# --- LLM Retry Configuration ---
LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "5"))
LLM_INITIAL_BACKOFF: float = float(os.getenv("LLM_INITIAL_BACKOFF", "1.0"))
LLM_MAX_BACKOFF: float = float(os.getenv("LLM_MAX_BACKOFF", "60.0"))

# LLM_MODE: live | dry_run | auto (auto = dry_run if no LLM API key, else live)
_LLM_MODE = os.getenv("LLM_MODE", "auto").strip().lower()


def get_llm_provider() -> str:
    """Determine which LLM provider to use."""
    if LLM_PROVIDER == "ollama":
        return "ollama"
    if LLM_PROVIDER == "groq":
        return "groq"
    if LLM_PROVIDER == "auto":
        # Prefer Ollama if available, otherwise Groq
        if _is_ollama_available():
            return "ollama"
        if GROQ_API_KEY:
            return "groq"
    return "ollama"  # Default to Ollama


def _is_ollama_available() -> bool:
    """Check if Ollama is available."""
    try:
        import requests
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


def has_llm_credentials() -> bool:
    provider = get_llm_provider()
    if provider == "ollama":
        return True  # Ollama doesn't need API keys
    return bool(GROQ_API_KEY)


def is_llm_dry_run() -> bool:
    if _LLM_MODE == "dry_run":
        return True
    if _LLM_MODE == "live":
        return False
    return not has_llm_credentials()
