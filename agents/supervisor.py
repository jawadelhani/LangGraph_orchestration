from langgraph.graph import END

from config import is_llm_dry_run
from graph.state import AgentState
from llm.llm_client import LLMQuotaError, call_llm


def _supervisor_dry_run(state: AgentState) -> dict:
    """Deterministic routing: fill backlog → plan sprint → assign → stop."""
    msg = (state.get("user_input") or "").strip().lower()
    if not msg or msg in ("thanks", "thank you", "ok", "bye"):
        return {"next_agent": END}

    backlog = state.get("backlog") or []
    sprint = state.get("sprint_plan") or []
    assigns = state.get("assignments") or []
    assigned_n = sum(1 for t in assigns if t.get("assignee_id"))

    if len(backlog) == 0:
        return {"next_agent": "task"}
    if len(sprint) == 0:
        return {"next_agent": "planning"}
    if assigned_n < len(sprint):
        return {"next_agent": "assignment"}
    return {"next_agent": END}


def supervisor_node(state: AgentState) -> dict:
    if state.get("error"):
        return {"next_agent": END}

    backlog = state.get("backlog") or []
    sprint = state.get("sprint_plan") or []
    assigns = state.get("assignments") or []
    backlog_n = len(backlog)
    sprint_n = len(sprint)
    assign_n = len(assigns)
    assigned_n = sum(1 for t in assigns if t.get("assignee_id"))

    # early-exit: all three stages done
    if backlog_n > 0 and sprint_n > 0 and assigned_n >= sprint_n:
        return {"next_agent": END}

    if is_llm_dry_run():
        return _supervisor_dry_run(state)

    prompt = f"""You route user messages to exactly one worker. Reply with ONE word only.

User message: {state.get("user_input", "")!r}

Counts: backlog_tasks={backlog_n}, sprint_plan_tasks={sprint_n}, assignment_tasks={assign_n}

Rules:
- task — new features, requirements, user stories.
- planning — sprint planning, prioritization. Needs backlog > 0.
- assignment — assign tasks. Needs sprint_plan > 0.
- end — nothing to do or pipeline done.

If user wants a full chain: backlog>0 but no sprint → planning; sprint>0 but no assignments → assignment.

One word only: task | planning | assignment | end
"""
    try:
        first = call_llm(prompt).strip().lower().split()
    except LLMQuotaError as e:
        return {"next_agent": END, "error": str(e)}

    raw = (first[0] if first else "").strip(".,|!?:;")
    if raw in ("task", "planning", "assignment"):
        return {"next_agent": raw}
    if raw == "po":
        return {"next_agent": "task"}
    return {"next_agent": END}