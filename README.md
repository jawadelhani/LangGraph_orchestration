# PM agents — LangGraph workflow (Gemini + PostgreSQL)

Autonomous **Task**, **Planning**, and **Assignment** agents share one **LangGraph** workflow. A **Supervisor** node (Gemini) routes each user message to exactly one agent. Agents follow an **AgileAI-style** pattern: `BaseAgent` with `system_prompt()`, `tool_definitions()`, `execute_tool()`, and `run()`.

There is **no HTTP API** in this repo—only `python main.py` and tests.

## Layout

- `main.py` — create tables, build graph, `invoke()` with sample state  
- `config.py`, `.env` / `.env.example` — `LLM_MODE` (`live` / `dry_run` / `auto`), `GEMINI_API_KEY`, `DATABASE_URL`, `GEMINI_MODEL`  
- `graph/` — `state.py`, `router.py`, `graph_builder.py`  
- `agents/base.py` — shared agent contract  
- `agents/task_agent.py` — backlog / stories (tools: search tasks, project context)  
- `agents/planning_agent.py` — sprint plan + goal (tools: backlog, velocity, capacity)  
- `agents/assignment_agent.py` — assign + reviewer + next actions (tools: workload, skills, task details)  
- `agents/supervisor.py` — routes: `task` | `planning` | `assignment` | end  
- `db/` — SQLAlchemy models (`tasks`, `sprint_plans`, `assignments`, `velocity_history`), `persist.py`  
- `llm/gemini_client.py` — Gemini client only  
- `llm/json_util.py` — `parse_json_blob` (no Google import; used in tests)  

## Prerequisites

- Python 3.10+ (3.11+ recommended)  
- PostgreSQL instance and a database (e.g. `pm_agents`)  
- A [Gemini API key](https://ai.google.dev/) only if you use `LLM_MODE=live`  

## Gemini quota (429)

If you see **ResourceExhausted / 429**, your project has hit free-tier limits for that model. You can:

1. Set **`LLM_MODE=dry_run`** in `.env` — the graph still runs end-to-end with **fake but valid** task/plan/assignment data (no API calls).  
2. Try another **`GEMINI_MODEL`** (see `.env.example`; the code defaults to `gemini-1.5-flash`).  
3. Wait for the reset, enable billing, or check [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits).  

With **`LLM_MODE=auto`** (default), the app uses **dry_run when there is no API key**, and **live** when a key is set.

## Setup

1. Clone or copy the project and open a terminal at the project root.  
2. Create a virtual environment (optional but recommended).  
3. Install dependencies:

```powershell
pip install -r requirements.txt
```

4. Copy `.env.example` to `.env` and set:

- `LLM_MODE` — optional: `live`, `dry_run`, or `auto` (default)  
- `GEMINI_API_KEY` — required only for `live`  
- `DATABASE_URL` — e.g. `postgresql+psycopg2://USER:PASSWORD@localhost:5432/pm_agents`  
- `GEMINI_MODEL` — optional; default is `gemini-1.5-flash`  

5. Ensure PostgreSQL is running and the database exists (`CREATE DATABASE pm_agents;`).

## Database

On first run, `init_db()` calls SQLAlchemy `create_all()`.

If you already had an older schema in this project, **drop the old tables** or use a fresh database so new columns (`project_id`, `status`, `reviewer_id`, etc.) match `db/models.py`.

## How to test

### 1. Unit tests (no Gemini, no PostgreSQL)

These cover the router and JSON parsing helpers only:

```powershell
python -m pytest tests -q
```

`pytest.ini` turns off the long warning summary (LangGraph / deprecated `google.generativeai`). To see them again: `python -m pytest tests -q -W default`.

### 2. End-to-end workflow (PostgreSQL; Gemini optional)

```powershell
python main.py
```

The script prints `LLM: dry_run ...` or `LLM: live ...` on stderr. With **`LLM_MODE=dry_run`** (or **auto** without an API key), it **does not call Gemini** and still fills backlog → sprint → assignments.

You should see JSON for `backlog`, `sprint_plan`, `assignments`, and any `error`. Check PostgreSQL:

- `tasks` — stories with `project_id`, `priority`, `labels`, etc.  
- `sprint_plans` — ordered `task_ids_ordered`, optional `goal`, `meta`  
- `assignments` — `task_id`, `assignee_id`, optional `reviewer_id`  

### 3. One agent at a time (manual state)

Call `graph.invoke()` with a smaller `user_input` and only the counts you need, for example:

- Only Task Agent: *“We need OAuth login.”* (supervisor → `task` → end)  
- Planning: pass a state object that already has a non-empty `backlog`  
- Assignment: pass non-empty `sprint_plan` and `team_members`  

Always set `project_id` in state (default in `main.py` is `default`).

## Agent design (vs hybrid backend)

- **Orchestration:** Supervisor + LangGraph is easier to trace than peer-to-peer agent chatter.  
- **Data:** One PostgreSQL with shared tables; each agent owns specific writes (`persist.py`).  
- **Hybrid later:** You can wrap the same graph behind FastAPI and add validation/approval like your `orchestrator` sketch—this repo keeps the core workflow isolated on purpose.
