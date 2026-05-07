"""
Task Agent
- Generates tasks from natural language input
- Improves task descriptions with acceptance criteria
- Auto-prioritizes (P1–P4)
- Detects duplicate tasks via search
- Suggests splitting large tasks
"""

import json

from base import BaseAgent
from db import get_agent_db
from models import Task


class TaskAgent(BaseAgent):
    name = "task_agent"
    description = "Generates, improves, prioritizes and deduplicates tasks."

    def system_prompt(self) -> str:
        return """
You are the Task Agent for AgileAI, an AI-powered agile project management system.

Your responsibilities:
1. Generate well-structured tasks from user input or feature descriptions.
2. Improve task descriptions: add clear steps, acceptance criteria, and definition of done.
3. Auto-assign priority: P1 (Critical), P2 (High), P3 (Medium), P4 (Low).
4. Detect duplicate tasks by searching the existing task list.
5. Suggest splitting tasks that are too large (would take more than 2 days).

Output rules:
- Always use the provided tools to search for duplicates before creating a task.
- Return structured JSON for every task you create or improve.
- Be concise in descriptions — clear, actionable language only.
- Acceptance criteria must be testable (Given/When/Then format preferred).
- Priority rules:
    P1 = blocks release or other team members
    P2 = important for current sprint
    P3 = should be done soon, not blocking
    P4 = nice to have / backlog

When you have finished processing, return a JSON block with this exact structure:
{
  "action": "create" | "improve" | "split",
  "tasks": [
    {
      "title": "...",
      "description": "...",
      "acceptance_criteria": ["...", "..."],
      "priority": "P1" | "P2" | "P3" | "P4",
      "labels": ["...", "..."],
      "estimated_hours": number,
      "duplicate_of": null | "existing_task_id",
      "split_from": null | "parent_task_title"
    }
  ],
  "warnings": ["..."]
}
"""

    def tool_definitions(self) -> list[dict]:
        return [
            {
                "name": "search_existing_tasks",
                "description": "Search existing tasks in the project to detect duplicates or related work.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string", "description": "The project ID to search within."},
                        "query": {"type": "string", "description": "Search query — keywords from the task title or description."},
                    },
                    "required": ["project_id", "query"],
                },
            },
            {
                "name": "get_project_context",
                "description": "Get project metadata: current sprint, team size, tech stack labels.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string", "description": "The project ID."},
                    },
                    "required": ["project_id"],
                },
            },
        ]

    def execute_tool(self, name: str, args: dict):
        db = get_agent_db()
        try:
            if name == "search_existing_tasks":
                project_id = args["project_id"]
                query = args["query"].lower()
                tasks = db.query(Task).filter(Task.project_id == project_id).all()
                matches = [
                    {"id": str(t.id), "title": t.title, "status": t.status, "priority": t.priority}
                    for t in tasks
                    if query in t.title.lower() or (t.description and query in t.description.lower())
                ]
                return {"matches": matches, "total_found": len(matches)}

            if name == "get_project_context":
                # In production: query project + sprint tables
                # Returning mock structure for now
                return {
                    "project_id": args["project_id"],
                    "current_sprint": "Sprint 3",
                    "team_size": 5,
                    "common_labels": ["frontend", "backend", "api", "ui", "auth", "bug", "feature", "infra"],
                }
        finally:
            db.close()

        return {"error": f"Unknown tool: {name}"}
