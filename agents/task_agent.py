"""
Task Agent — backlog / user stories from natural language.

- Generates tasks from natural language input
- Improves descriptions with acceptance criteria
- Auto-prioritizes (P1–P4)
- Detects duplicate tasks via search tool
- Suggests splitting large tasks
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import func, select

from agents.base import BaseAgent
from config import is_llm_dry_run
from db.models import TaskRow
from db.persist import save_backlog
from db.session import session_scope
from graph.state import AgentState, TaskDict
from llm.json_util import parse_json_blob


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
4. Respect duplicate hints from duplicate_search in Context.
5. Suggest splitting tasks that are too large (would take more than 2 days).

Rules:
- Be concise — clear, actionable language only.
- Acceptance criteria must be testable (Given/When/Then preferred).
- Priority:
  P1 = blocks release or other team members
  P2 = important for current sprint
  P3 = should be done soon, not blocking
  P4 = nice to have / backlog

Return ONLY valid JSON (no markdown), exactly:
{
  "action": "create" | "improve" | "split",
  "tasks": [
    {
      "title": "...",
      "description": "...",
      "acceptance_criteria": ["..."],
      "priority": "P1" | "P2" | "P3" | "P4",
      "labels": ["..."],
      "estimated_hours": null,
      "duplicate_of": null,
      "split_from": null
    }
  ],
  "warnings": []
}
"""

    def tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "search_existing_tasks",
                "description": "Search existing tasks in the project to detect duplicates or related work.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "query": {"type": "string"},
                    },
                    "required": ["project_id", "query"],
                },
            },
            {
                "name": "get_project_context",
                "description": "Project metadata: task counts and labels distribution.",
                "parameters": {
                    "type": "object",
                    "properties": {"project_id": {"type": "string"}},
                    "required": ["project_id"],
                },
            },
        ]

    def execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name == "search_existing_tasks":
            project_id = str(args["project_id"])
            query = str(args["query"]).lower().strip()
            matches: list[dict[str, Any]] = []
            with session_scope() as s:
                stmt = select(TaskRow).where(TaskRow.projectId == project_id).limit(500)
                for t in s.scalars(stmt):
                    title_l = (t.title or "").lower()
                    desc_l = (t.description or "").lower()
                    if query in title_l or (t.description and query in desc_l):
                        matches.append(
                            {
                                "id": t.id,
                                "title": t.title,
                                "status": t.status,
                                "priority": t.priority,
                            }
                        )
            return {"matches": matches, "total_found": len(matches)}

        if name == "get_project_context":
            project_id = str(args["project_id"])
            with session_scope() as s:
                n = s.scalar(select(func.count()).select_from(TaskRow).where(TaskRow.projectId == project_id))
            return {
                "project_id": project_id,
                "open_task_count": int(n or 0),
                "common_labels": ["frontend", "backend", "api", "ui", "auth", "bug", "feature", "infra"],
            }

        return super().execute_tool(name, args)

    def run(self, user_input: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = dict(context or {})
        project_id = str(ctx.get("project_id") or "default")
        ctx["duplicate_search"] = self.execute_tool(
            "search_existing_tasks",
            {"project_id": project_id, "query": user_input[:280]},
        )
        ctx["project_context"] = self.execute_tool("get_project_context", {"project_id": project_id})
        return super().run(user_input, ctx)


def _dry_task_json(state: AgentState) -> dict[str, Any]:
    raw_req = (state.get("user_input") or "New feature").strip()[:300]
    return {
        "action": "create",
        "tasks": [
            {
                "title": "Implement requested feature",
                "description": f"As a user, I want the described capability so that I can use the product. Context: {raw_req}",
                "acceptance_criteria": [
                    "Given valid input, when the user performs the main flow, then the feature works without errors.",
                ],
                "priority": "P2",
                "labels": ["feature", "dry-run"],
                "estimated_hours": None,
                "duplicate_of": None,
                "split_from": None,
            }
        ],
        "warnings": ["dry_run: no API call"],
    }


def task_node(state: AgentState) -> dict[str, Any]:
    project_id = state.get("project_id") or "default"
    if is_llm_dry_run():
        data = _dry_task_json(state)
    else:
        agent = TaskAgent()
        out = agent.run(state.get("user_input", ""), {"project_id": project_id})
        if err := out.get("llm_error"):
            return {"error": err}
        raw = out.get("raw_output") or ""
        try:
            data = parse_json_blob(raw)
        except json.JSONDecodeError as e:
            return {"error": f"Task agent returned invalid JSON: {e}"}
    tasks_in = data.get("tasks") if isinstance(data, dict) else None
    if not isinstance(tasks_in, list):
        return {"error": "Task agent expected JSON with a tasks array."}

    backlog: list[TaskDict] = []
    for it in tasks_in:
        backlog.append(
            {
                "id": str(uuid.uuid4()),
                "project_id": project_id,
                "title": str(it.get("title", "")),
                "description": str(it.get("description", "")),
                "acceptance_criteria": list(it.get("acceptance_criteria") or []),
                "story_points": it.get("story_points"),
                "priority": it.get("priority"),
                "labels": list(it.get("labels") or []),
                "estimated_hours": it.get("estimated_hours"),
                "status": "backlog",
                "ai_generated": True,
            }
        )

    save_backlog(backlog, default_project_id=project_id)
    return {"backlog": backlog, "error": None}
