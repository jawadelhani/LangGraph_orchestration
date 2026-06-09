from __future__ import annotations
import json
import logging
from config import GROQ_MODEL, is_llm_dry_run
from db.persist import ensure_project, ensure_users
from db.session import init_db
from graph.graph_builder import build_graph
from main import build_initial_state

# Set up logging to console
logging.basicConfig(level=logging.INFO)

def test_run():
    init_db()
    graph = build_graph()
    
    state = build_initial_state(
        "We need a login page with Google OAuth. Plan the sprint and assign tasks to the team.",
        project_id="demo-project",
        team_members=[
            {"id": "user_2PwZmH2xP5aE0svR6hDH4AwDlcu", "name": "Joe Rogan", "skills": ["React", "OAuth", "frontend"], "current_load": 3},
            {"id": "user_2PwYvTgm6kvgJIbWwN0xsei8izu", "name": "Steve Jobs", "skills": ["backend", "FastAPI", "PostgreSQL"], "current_load": 5},
        ]
    )
    
    # Enable skip_db_write
    state["skip_db_write"] = True
    
    ensure_project(state["project_id"], name="Demo project")
    ensure_users(state["team_members"])
    
    # We stream the graph execution to print every transition and state update
    print("--- Starting LangGraph Execution ---")
    step = 0
    for event in graph.stream(state, {"recursion_limit": 30}):
        step += 1
        print(f"\n=== STEP {step} ===")
        for node_name, output in event.items():
            print(f"Node executed: {node_name}")
            # Print keys that were updated
            print(f"Keys updated: {list(output.keys())}")
            if "next_agent" in output:
                print(f"  next_agent: {output['next_agent']}")
            if "error" in output and output["error"]:
                print(f"  error: {output['error']}")
            if "backlog" in output:
                print(f"  backlog tasks: {len(output['backlog'])}")
            if "sprint_plan" in output:
                print(f"  sprint_plan tasks: {len(output['sprint_plan'])}")
            if "assignments" in output:
                print(f"  assignments tasks: {len(output['assignments'])}")
            
if __name__ == "__main__":
    test_run()
