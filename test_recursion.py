"""Test script to diagnose the recursion issue."""
import os
import sys
sys.path.insert(0, '.')

# Force dry-run mode to avoid API rate limits
os.environ["LLM_MODE"] = "dry_run"

from main import build_initial_state, build_graph
from db.persist import ensure_project, ensure_users

# Test with the actual users from the database
team_members = [
    {
        "id": "user_2PvBRngdvenUlFvQNAWbXIvYVy5",
        "name": "Sheldon Cooper",
        "skills": ["backend", "Python", "PostgreSQL"],
        "current_load": 0
    },
    {
        "id": "user_2PwZmH2xP5aE0svR6hDH4AwDlcu",
        "name": "Joe Rogan",
        "skills": ["frontend", "React", "UI"],
        "current_load": 0
    },
    {
        "id": "user_2PwYvTgm6kvgJIbWwN0xsei8izu",
        "name": "Steve Jobs",
        "skills": ["product", "design", "strategy"],
        "current_load": 0
    }
]

project_id = "init-project-id-dq8yh-d0as89hjd"

print("Building initial state...")
state = build_initial_state(
    user_input="We need a login page with Google OAuth. Plan the sprint and assign tasks.",
    project_id=project_id,
    team_members=team_members
)
state["skip_db_write"] = True

print("Ensuring project and users exist in DB...")
ensure_project(project_id, name="Test Project")
ensure_users(team_members)

print("Building graph...")
graph = build_graph()

print("Invoking graph with recursion_limit=50...")
try:
    out = graph.invoke(state, {"recursion_limit": 50})
    print("\n=== SUCCESS ===")
    print(f"Backlog items: {len(out.get('backlog', []))}")
    print(f"Sprint plan items: {len(out.get('sprint_plan', []))}")
    print(f"Assignments: {len(out.get('assignments', []))}")
    print(f"Error: {out.get('error')}")
except Exception as e:
    print(f"\n=== ERROR ===")
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
