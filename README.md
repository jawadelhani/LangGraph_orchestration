# PM agents — LangGraph workflow (Groq / Gemini + PostgreSQL)

Autonomous **Task**, **Planning**, and **Assignment** agents share one **LangGraph** workflow. A **Supervisor** routes each user message to exactly one agent (same prompts work with **Groq** or **Gemini**).

**Recommended:** [Groq](https://console.groq.com/home) — generous free tier (see their [docs](https://console.groq.com/docs/rate-limits)). Default model: `llama-3.3-70b-versatile`.

There is **no HTTP API** in this repo—only `python main.py` and tests.

## Layout

- `main.py` — create tables, build graph, `invoke()` with sample state  
- `config.py`, `.env` / `.env.example` — `LLM_MODE`, `LLM_PROVIDER`, `GROQ_*`, optional `GEMINI_*`, `DATABASE_URL`  
- `graph/` — `state.py`, `router.py`, `graph_builder.py`  
- `agents/` — task, planning, assignment, supervisor  
- `db/` — SQLAlchemy models, `persist.py`  
- `llm/llm_client.py` — **`call_llm()`** → Groq (OpenAI-compatible) or Gemini  
- `llm/json_util.py` — `parse_json_blob` (tests only; no cloud import)  

## Prerequisites

- Python 3.10+  
- PostgreSQL  
- **Either** `GROQ_API_KEY` **or** `GEMINI_API_KEY` for live inference (Groq is preferred when both exist and `LLM_PROVIDER=auto`)

## Setup

```powershell
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env`:

| Variable | Purpose |
|----------|---------|
| `GROQ_API_KEY` | From [Groq API Keys](https://console.groq.com/keys) |
| `GROQ_MODEL` | e.g. `llama-3.3-70b-versatile` or `mixtral-8x7b-32768` |
| `LLM_PROVIDER` | `auto` (default: Groq if key present), `groq`, or `gemini` |
| `LLM_MODE` | `auto`, `live`, or `dry_run` |
| `DATABASE_URL` | PostgreSQL connection string |

## Gemini quota (429)

If you still use Gemini and hit **429**, switch to Groq (`GROQ_API_KEY`) or use **`LLM_MODE=dry_run`** for offline deterministic runs.

With **`LLM_MODE=auto`**, you get **dry_run** when **no** Groq **and** no Gemini key is set; **live** when at least one key is set (Groq wins in `auto` provider resolution).

## Database

`init_db()` uses `create_all()`. If an old schema exists, migrate or use a fresh DB.

## How to test

```powershell
python -m pytest tests -q
python main.py
```

Stderr shows e.g. `LLM: live (Groq / llama-3.3-70b-versatile)` or `LLM: dry_run (no API calls)`.

## Security

Never commit `.env` or paste API keys in chat. If a key was exposed, **revoke it** in the provider console and create a new one.
