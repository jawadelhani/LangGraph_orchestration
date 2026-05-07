"""Application configuration loaded from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyC5CHxfA5tMbaPbRiRIP8JTZAl4kwLp5B0")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
AGENT_DB_URL = os.getenv("AGENT_DB_URL", "postgresql://user:root@localhost:5432/AGENT_DB")
USER_DB_URL = os.getenv("USER_DB_URL", "postgresql://user:root@localhost:5432/USER_DB")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
