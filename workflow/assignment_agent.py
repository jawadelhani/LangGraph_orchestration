"""
Assignment Agent
- Checks current workload per team member
- Auto-assigns tasks based on skills + availability
- Suggests reviewers
- Recommends next actions per user
"""

import json

from base import BaseAgent
from db import get_agent_db, get_user_db
from models import Task, TeamMember, Skill, SprintTask


class AssignmentAgent(BaseAgent):
    name = "assignment_agent"
    description = "Assigns tasks to team members based on skills, workload, and availability."

    def system_prompt(self) -> str:
        return """
You are the Assignment Agent for AgileAI, an AI-powered agile project management system.

Your responsibilities:
1. Analyze team member workloads (how many tasks, how many story points already assigned).
2. Match task requirements to team member skills.
3. Assign the most suitable team member to a task.
4. Suggest a reviewer (different from the assignee, with relevant skills).
5. Recommend the next task a specific user should work on.

Assignment logic:
- Never assign to someone already at 100% capacity (>=8 story points in current sprint).
- Prefer members whose skill level matches the task complexity.
- If two members are equally qualified, prefer the one with lower current load.
- Always explain your reasoning briefly.

Output structure (return as JSON):
{
  "action": "assign" | "suggest_reviewer" | "next_action",
  "assignments": [
    {
      "task_id": "...",
      "task_title": "...",
      "assigned_to": {
        "user_id": "...",
        "name": "...",
        "reason": "..."
      },
      "reviewer": {
        "user_id": "...",
        "name": "...",
        "reason": "..."
      }
    }
  ],
  "next_actions": [
    {
      "user_id": "...",
      "recommended_task_id": "...",
      "recommended_task_title": "...",
      "reason": "..."
    }
  ],
  "warnings": ["..."]
}
"""

    def tool_definitions(self) -> list[dict]:
        return [
            {
                "name": "get_team_workload",
                "description": "Get current story point load for each team member in the active sprint.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "sprint_id": {"type": "string", "description": "Active sprint ID. Optional — uses current sprint if omitted."},
                    },
                    "required": ["project_id"],
                },
            },
            {
                "name": "get_skill_matrix",
                "description": "Get the skill matrix for all members of a team.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                    },
                    "required": ["project_id"],
                },
            },
            {
                "name": "get_task_details",
                "description": "Get full details of a task including labels and estimated hours.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                    },
                    "required": ["task_id"],
                },
            },
        ]

    def execute_tool(self, name: str, args: dict):
        agent_db = get_agent_db()
        user_db = get_user_db()
        try:
            if name == "get_team_workload":
                project_id = args["project_id"]
                # Query assigned story points per member in current sprint
                members = user_db.query(TeamMember).filter(TeamMember.project_id == project_id).all()
                workload = []
                for m in members:
                    assigned_tasks = agent_db.query(Task).filter(
                        Task.assignee_id == m.user_id,
                        Task.project_id == project_id,
                        Task.status.in_(["todo", "in_progress"]),
                    ).all()
                    total_points = sum(t.story_points or 0 for t in assigned_tasks)
                    workload.append({
                        "user_id": str(m.user_id),
                        "name": m.name,
                        "role": m.role,
                        "assigned_points": total_points,
                        "capacity_points": 8,  # default sprint capacity per person
                        "available_points": max(0, 8 - total_points),
                        "task_count": len(assigned_tasks),
                    })
                return {"workload": workload}

            if name == "get_skill_matrix":
                project_id = args["project_id"]
                members = user_db.query(TeamMember).filter(TeamMember.project_id == project_id).all()
                matrix = []
                for m in members:
                    skills = user_db.query(Skill).filter(Skill.user_id == m.user_id).all()
                    matrix.append({
                        "user_id": str(m.user_id),
                        "name": m.name,
                        "skills": [{"skill": s.skill_name, "level": s.level} for s in skills],
                    })
                return {"skill_matrix": matrix}

            if name == "get_task_details":
                task = agent_db.query(Task).filter(Task.id == args["task_id"]).first()
                if not task:
                    return {"error": "Task not found"}
                return {
                    "task_id": str(task.id),
                    "title": task.title,
                    "description": task.description,
                    "labels": task.labels or [],
                    "priority": task.priority,
                    "story_points": task.story_points,
                    "estimated_hours": task.estimated_hours,
                }
        finally:
            agent_db.close()
            user_db.close()

        return {"error": f"Unknown tool: {name}"}
