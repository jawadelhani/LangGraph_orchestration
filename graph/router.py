from langgraph.graph import END

from graph.state import AgentState


def route(state: AgentState) -> str:
    target = state.get("next_agent", END)
    if target in ("task", "planning", "assignment"):
        return target
    return END
