"""
Planning Agent (Sprint Planning)
- Auto-estimates story points based on velocity history
- Suggests optimal task set for a sprint given team capacity
- Generates a clear sprint goal
- Detects tasks that are too large and suggests splitting
"""

import json

from base import BaseAgent
from db import get_agent_db
from models import Task, Sprint, SprintTask, VelocityHistory


class PlanningAgent(BaseAgent):
    name = "planning_agent"
    description = "Plans sprints: estimates story points, selects tasks, generates sprint goals."

    def system_prompt(self) -> str:
        return """
You are the Planning Agent for AgileAI, an AI-powered agile project management system.

Your responsibilities:
1. Estimate story points for tasks in the backlog using complexity signals and velocity history.
2. Select the optimal set of tasks for the upcoming sprint given team capacity.
3. Generate a clear, concise sprint goal (1–2 sentences, outcome-focused).
4. Flag tasks that are too large (>8 points) and suggest how to split them.

Estimation rules (Fibonacci scale: 1, 2, 3, 5, 8, 13):
- 1: Trivial change, <1 hour
- 2: Simple task, well understood, <half day
- 3: Small feature, some unknowns, ~1 day
- 5: Medium feature, some complexity, 2–3 days
- 8: Large feature or significant unknowns, ~1 week
- 13: Too large — must be split before sprint planning

Task selection rules:
- Total sprint points must not exceed team_capacity (sum of all member available points).
- Prioritize P1 tasks first, then P2, then P3.
- Leave 10–15% buffer for unplanned work (bugs, support).
- Never include tasks with blockers or missing acceptance criteria.

Sprint goal rules:
- Focus on the business outcome, not the list of tasks.
- Must be achievable within the sprint.
- Format: "By the end of this sprint, [team] will have [outcome] so that [value]."

Output structure (return as JSON):
{
  "action": "plan_sprint",
  "sprint": {
    "name": "Sprint N",
    "goal": "...",
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD",
    "total_capacity_points": number,
    "planned_points": number,
    "buffer_points": number
  },
  "selected_tasks": [
    {
      "task_id": "...",
      "title": "...",
      "priority": "...",
      "estimated_points": number,
      "reason_included": "..."
    }
  ],
  "excluded_tasks": [
    {
      "task_id": "...",
      "title": "...",
      "reason_excluded": "..."
    }
  ],
  "tasks_to_split": [
    {
      "task_id": "...",
      "title": "...",
      "current_estimate": number,
      "split_suggestion": ["subtask 1 description", "subtask 2 description"]
    }
  ],
  "warnings": ["..."]
}
"""

    def tool_definitions(self) -> list[dict]:
        return [
            {
                "name": "get_backlog",
                "description": "Get all tasks in the backlog (not yet assigned to a sprint), ordered by priority.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "limit": {"type": "integer", "description": "Max tasks to return. Default 50."},
                    },
                    "required": ["project_id"],
                },
            },
            {
                "name": "get_velocity_history",
                "description": "Get the last N sprints' velocity (planned vs completed story points).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "last_n_sprints": {"type": "integer", "description": "Number of past sprints to analyze. Default 5."},
                    },
                    "required": ["project_id"],
                },
            },
            {
                "name": "get_team_capacity",
                "description": "Get total available story points for the team in the upcoming sprint.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "sprint_duration_days": {"type": "integer", "description": "Sprint duration in working days. Default 10."},
                    },
                    "required": ["project_id"],
                },
            },
        ]

    def execute_tool(self, name: str, args: dict):
        db = get_agent_db()
        try:
            if name == "get_backlog":
                project_id = args["project_id"]
                limit = args.get("limit", 50)
                tasks = (
                    db.query(Task)
                    .filter(Task.project_id == project_id, Task.sprint_id == None, Task.status == "backlog")
                    .order_by(Task.priority.asc())
                    .limit(limit)
                    .all()
                )
                return {
                    "backlog": [
                        {
                            "task_id": str(t.id),
                            "title": t.title,
                            "priority": t.priority,
                            "story_points": t.story_points,
                            "labels": t.labels or [],
                            "estimated_hours": t.estimated_hours,
                            "has_acceptance_criteria": bool(t.acceptance_criteria),
                        }
                        for t in tasks
                    ]
                }

            if name == "get_velocity_history":
                project_id = args["project_id"]
                n = args.get("last_n_sprints", 5)
                history = (
                    db.query(VelocityHistory)
                    .filter(VelocityHistory.project_id == project_id)
                    .order_by(VelocityHistory.created_at.desc())
                    .limit(n)
                    .all()
                )
                records = [
                    {
                        "sprint_id": str(h.sprint_id),
                        "planned_points": h.planned_points,
                        "completed_points": h.completed_points,
                        "completion_rate": round(h.completed_points / h.planned_points, 2) if h.planned_points else 0,
                    }
                    for h in history
                ]
                avg_velocity = (
                    round(sum(r["completed_points"] for r in records) / len(records), 1)
                    if records else 0
                )
                return {"velocity_history": records, "average_velocity": avg_velocity}

            if name == "get_team_capacity":
                project_id = args["project_id"]
                sprint_days = args.get("sprint_duration_days", 10)
                # In production: query team members + leave calendar
                # Points per person per sprint = 8 (default)
                # Mocked with 5 members for now
                member_count = 5
                total_capacity = member_count * 8
                buffer = int(total_capacity * 0.15)
                return {
                    "project_id": project_id,
                    "sprint_duration_days": sprint_days,
                    "member_count": member_count,
                    "total_capacity_points": total_capacity,
                    "buffer_points": buffer,
                    "available_points": total_capacity - buffer,
                }
        finally:
            db.close()

        return {"error": f"Unknown tool: {name}"}
