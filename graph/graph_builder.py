from langgraph.graph import END, StateGraph

from agents.assignment_agent import assignment_node
from agents.planning_agent import planning_node
from agents.task_agent import task_node
from agents.supervisor import supervisor_node
from graph.router import route
from graph.state import AgentState


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("supervisor", supervisor_node)
    g.add_node("task", task_node)
    g.add_node("planning", planning_node)
    g.add_node("assignment", assignment_node)

    g.set_entry_point("supervisor")
    g.add_conditional_edges(
        "supervisor",
        route,
        {
            "task": "task",
            "planning": "planning",
            "assignment": "assignment",
            END: END,
        },
    )
    g.add_edge("task", "supervisor")
    g.add_edge("planning", "supervisor")
    g.add_edge("assignment", "supervisor")
    return g.compile()
