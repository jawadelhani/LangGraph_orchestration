from __future__ import annotations

import json
import sys
import warnings

# Quiet noisy third-party warnings when running the script (pytest uses pytest.ini).
warnings.filterwarnings(
    "ignore",
    message="All support for the `google.generativeai`",
    category=FutureWarning,
)
warnings.filterwarnings(
    "ignore",
    message="Core Pydantic V1 functionality isn't compatible",
    category=UserWarning,
)
warnings.filterwarnings(
    "ignore",
    message="The default value of `allowed_objects`",
    category=UserWarning,
)

from config import GROQ_MODEL, is_llm_dry_run
from db.persist import ensure_project, ensure_users
from db.session import init_db
from graph.graph_builder import build_graph
from graph.state import TeamMemberDict

DEFAULT_TEAM: list[TeamMemberDict] = [
    {"id": "u1", "name": "Fatima", "skills": ["React", "OAuth", "frontend"], "current_load": 3},
    {"id": "u2", "name": "Youssef", "skills": ["backend", "FastAPI", "PostgreSQL"], "current_load": 5},
]


def build_initial_state(
    user_input: str,
    *,
    project_id: str = "default",
    team_members: list[TeamMemberDict] | None = None,
) -> dict:
    return {
        "user_input": user_input,
        "project_id": project_id,
        "backlog": [],
        "sprint_plan": [],
        "assignments": [],
        "team_members": team_members or DEFAULT_TEAM,
        "error": None,
    }


def main() -> None:
    if is_llm_dry_run():
        line = "LLM: dry_run (no API calls)"
    else:
        line = f"LLM: live (Groq / {GROQ_MODEL})"
    print(line, file=sys.stderr)
    init_db()
    graph = build_graph()
    state = build_initial_state(
        "We need a login page with OAuth. Plan the sprint and assign tasks to the team.",
        project_id="demo-project",
    )
    # FK safety: make sure referenced rows exist
    ensure_project(state["project_id"], name="Demo project")
    ensure_users(state["team_members"])
    out = graph.invoke(state, {"recursion_limit": 25})
    keys = ("backlog", "sprint_plan", "assignments", "sprint_goal", "planning_extra", "assignment_extra", "error")
    print(json.dumps({k: out.get(k) for k in keys}, indent=2, default=str))


if __name__ == "__main__":
    main()
