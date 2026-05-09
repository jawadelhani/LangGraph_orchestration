from langgraph.graph import END

from graph.router import route


def test_route_agents():
    assert route({"next_agent": "task"}) == "task"
    assert route({"next_agent": "planning"}) == "planning"
    assert route({"next_agent": "assignment"}) == "assignment"


def test_route_defaults_to_end():
    assert route({}) is END
    assert route({"next_agent": "nope"}) is END
