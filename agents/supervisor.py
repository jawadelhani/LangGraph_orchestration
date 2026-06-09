from langgraph.graph import END
from graph.state import AgentState

def supervisor_node(state: AgentState) -> dict:
    if state.get("error"):
        return {"next_agent": END}

    backlog = state.get("backlog") or []
    sprint = state.get("sprint_plan") or []
    assigns = state.get("assignments") or []
    backlog_n = len(backlog)
    sprint_n = len(sprint)
    assigned_n = sum(1 for t in assigns if t.get("assignee_id"))

    # Sequential deterministic routing
    if backlog_n == 0:
        return {"next_agent": "task"}
    if sprint_n == 0:
        return {"next_agent": "planning"}
    if assigned_n < sprint_n:
        return {"next_agent": "assignment"}
    return {"next_agent": END}