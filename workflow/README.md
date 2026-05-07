# AgileAI — Agents Module

Three AI agents powered by **Gemini 2.0 Flash** with a full **human validation gate** before any data touches the database.

---

## Architecture

```
User input (text/audio)
        │
        ▼
  POST /ai/chat
        │
        ▼
  Orchestrator          ← classifies intent
        │
   ┌────┴──────────────────┐
   │                       │
Task Agent        Assignment Agent        Planning Agent
   │                       │                    │
   └────────────┬──────────┘                    │
                │                               │
           mapper.py   ←──────────────────────┘
                │
                ▼
       MapperResult (structured objects)
                │
                ▼
        store_validation()
                │
                ▼
     Redis + PostgreSQL (status=PENDING)
                │
                ▼
     ← returns validation_id to frontend ─────────┐
                                                   │
                                            Human reviews
                                         GET /validations/{id}
                                                   │
                                        PATCH /validations/{id}
                                        { "action": "approve" }
                                                   │
                                         write_*_to_db()
                                                   │
                                              Database ✓
```

---

## Install

```bash
pip install -r requirements.txt
```

Or manually:

```bash
pip install google-genai fastapi sqlalchemy psycopg2-binary redis python-dotenv
```

Create `.env`:

```
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.0-flash
AGENT_DB_URL=postgresql://user:pass@localhost:5432/agileai_agents
USER_DB_URL=postgresql://user:pass@localhost:5433/agileai_users
REDIS_URL=redis://localhost:6379/0
```

---

## Usage Examples

### 1. Task Agent — create tasks from natural language

```python
from task_agent import TaskAgent
from mapper import map_agent_output
from validation import store_validation

agent = TaskAgent()
result = agent.run(
    user_input="Create tasks for implementing JWT authentication in our FastAPI backend",
    context={"project_id": "proj_abc123"}
)

mapper_result = map_agent_output("task_agent", result["raw_output"], {"project_id": "proj_abc123"})
validation_id = store_validation(mapper_result, project_id="proj_abc123", requested_by="user_xyz")
print(f"Review at: GET /validations/{validation_id}")
```

### 2. Assignment Agent — auto-assign tasks

```python
from assignment_agent import AssignmentAgent

agent = AssignmentAgent()
result = agent.run(
    user_input="Assign the JWT auth tasks to the best available team member",
    context={"project_id": "proj_abc123", "task_ids": ["task_1", "task_2"]}
)
# → same flow: map → validate → approve
```

### 3. Planning Agent — plan a sprint

```python
from planning_agent import PlanningAgent

agent = PlanningAgent()
result = agent.run(
    user_input="Plan sprint 4 for our project. We have 5 developers for 2 weeks.",
    context={"project_id": "proj_abc123"}
)
# → same flow: map → validate → approve
```

---

## API Endpoints

| Method | Path                           | Description                              |
| ------ | ------------------------------ | ---------------------------------------- |
| POST   | `/ai/chat`                     | Send message, get validation_id back     |
| GET    | `/validations/{id}`            | Review agent output before writing to DB |
| PATCH  | `/validations/{id}`            | Approve / reject / edit-and-approve      |
| GET    | `/validations/?project_id=...` | List all pending validations             |

---

## Validation Decision Examples

```bash
# Approve as-is
PATCH /validations/abc-123
{ "action": "approve" }

# Reject
PATCH /validations/abc-123
{ "action": "reject", "reason": "Tasks are already covered in another ticket." }

# Edit then approve (human corrects AI output before saving)
PATCH /validations/abc-123
{
  "action": "edit_and_approve",
  "edited_tasks": [
    {
      "title": "Implement JWT token generation",
      "description": "...",
      "priority": "P1",
      "labels": ["backend", "auth"],
      "story_points": 5,
      "acceptance_criteria": [
        "Given a valid user, when login is called, then a signed JWT is returned",
        "Given an expired token, when a protected route is called, then 401 is returned"
      ]
    }
  ]
}
```

---

## Files

```
workflow-v1/
├── base.py              ← BaseAgent: google-genai loop, tool execution, session logging
├── task_agent.py        ← TaskAgent: generate, improve, deduplicate, prioritize
├── assignment_agent.py  ← AssignmentAgent: workload check, auto-assign, reviewer suggest
├── planning_agent.py    ← PlanningAgent: estimate, select tasks, generate sprint goal
├── mapper.py            ← Converts raw LLM JSON → typed Python objects
├── validation.py        ← Human gate: store pending, approve/reject, write to DB
├── orchestrator.py      ← FastAPI router: classify intent → run agent → return validation_id
├── models.py            ← SQLAlchemy ORM models (Agent DB + User DB)
├── config.py            ← Configuration: env vars
├── db.py                ← Database & Redis connection helpers
├── requirements.txt     ← Python dependencies
└── run.py               ← Example script
```
