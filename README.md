# PM agents — LangGraph workflow (Groq + PostgreSQL)

Autonomous **Task**, **Planning**, and **Assignment** agents share one **LangGraph** workflow. A **Supervisor** routes each user message to exactly one agent.

**Recommended:** [Groq](https://console.groq.com/home) — generous free tier (see their [docs](https://console.groq.com/docs/rate-limits)). Default model: `llama-3.3-70b-versatile`.

There is **no HTTP API** in this repo—only `python main.py` and tests.

## Layout

- `main.py` — create tables, build graph, `invoke()` with sample state  
- `config.py`, `.env` / `.env.example` — `LLM_MODE`, `GROQ_*`, `DATABASE_URL`  
- `graph/` — `state.py`, `router.py`, `graph_builder.py`  
- `agents/` — task, planning, assignment, supervisor  
- `db/` — SQLAlchemy models (`projects`, `users`, `tasks`, `sprint_plans`, `assignments`), `persist.py`  
- `llm/llm_client.py` — **`call_llm()`** → Groq (OpenAI-compatible API)  
- `llm/json_util.py` — `parse_json_blob` (tests only; no cloud import)  

## Prerequisites

- Python 3.10+  
- PostgreSQL  
- `GROQ_API_KEY` for live inference (or use `LLM_MODE=dry_run`)

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
| `LLM_MODE` | `auto`, `live`, or `dry_run` |
| `DATABASE_URL` | PostgreSQL connection string |

## Quota / rate limits (429)

If you hit **429**, wait and retry or switch to **`LLM_MODE=dry_run`** to run the full workflow without any API calls.

## Database

`init_db()` uses `create_all()`. If an old schema exists, migrate or use a fresh DB.

## How to test

```powershell
python -m pytest tests -q
python main.py
```

Stderr shows e.g. `LLM: live (Groq / llama-3.3-70b-versatile)` or `LLM: dry_run (no API calls)`.
