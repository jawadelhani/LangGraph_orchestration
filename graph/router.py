from langgraph.graph import END

from graph.state import AgentState


def route(state: AgentState):
    nxt = state.get("next_agent", END)
    # LLM sometimes returns the string "end" instead of the END constant
    if nxt in ("end", None, ""):
        return END
    if nxt in ("task", "planning", "assignment"):
        return nxt
    return END