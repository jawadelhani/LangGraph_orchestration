"""
Planning Agent — sprint planning with capacity, velocity hints, and sprint goal.

- Estimates story points using Fibonacci scale
- Selects tasks for the sprint given team capacity
- Generates sprint goal
- Flags tasks that are too large and should be split
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select

from agents.base import BaseAgent
from config import is_llm_dry_run
from db.models import TaskRow
from db.persist import save_sprint_plan
from db.session import session_scope
from graph.state import AgentState, TaskDict
from llm.json_util import parse_json_blob


class PlanningAgent(BaseAgent):
    name = "planning_agent"
    description = "Plans sprints: estimates story points, selects tasks, generates sprint goals."

    def system_prompt(self) -> str:
        return """
You are the Planning Agent for AgileAI, an AI-powered agile project management system.

Your responsibilities:
1. Estimate story points (Fibonacci: 1, 2, 3, 5, 8, 13) using backlog text and velocity hints.
2. Select an optimal task set for the upcoming sprint within available_points from Context.
3. Produce a concise sprint goal (outcome-focused, 1–2 sentences).
4. Flag tasks > 8 points as tasks_to_split.

Task selection rules:
- Respect available_points (capacity after buffer).
- Prefer higher priority (P1 before P4).
- Leave room for unplanned work (capacity already reflects buffer in Context when present).

Return ONLY valid JSON (no markdown), exactly:
{
  "action": "plan_sprint",
  "sprint": {
    "name": "Sprint N",
    "goal": "...",
    "start_date": null,
    "end_date": null,
    "total_capacity_points": 0,
    "planned_points": 0,
    "buffer_points": 0
  },
  "selected_tasks": [
    {
      "task_id": "...",
      "title": "...",
      "priority": "...",
      "estimated_points": 3,
      "reason_included": "..."
    }
  ],
  "excluded_tasks": [{"task_id": "...", "title": "...", "reason_excluded": "..."}],
  "tasks_to_split": [],
  "warnings": []
}
Use task_id values from backlog/context when possible; if unknown, use title match only (task_id null).
"""

    def tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "get_backlog",
                "description": "Backlog tasks for a project (status=backlog), ordered by priority.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["project_id"],
                },
            },
            {
                "name": "get_team_capacity",
                "description": "Team capacity for the upcoming sprint (story points).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "sprint_duration_days": {"type": "integer"},
                    },
                    "required": ["project_id"],
                },
            },
        ]

    def execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        project_id = str(args["project_id"])
        if name == "get_backlog":
            limit = int(args.get("limit") or 50)
            prio_order = {"P1": 0, "P2": 1, "P3": 2, "P4": 3, None: 9}

            snapshots: list[dict[str, Any]] = []
            with session_scope() as s:
                stmt = (
                    select(TaskRow)
                    .where(TaskRow.projectId == project_id, TaskRow.status.in_(["BACKLOG", "backlog"]))
                    .limit(limit * 3)
                )
                for r in s.scalars(stmt):
                    snapshots.append(
                        {
                            "task_id": r.id,
                            "title": r.title,
                            "priority": r.priority,
                            "story_points": r.storyPoints,
                            "labels": list(r.labels or []),
                            "estimated_hours": r.estimatedHours,
                            "has_acceptance_criteria": bool(r.acceptanceCriteria),
                        }
                    )
            snapshots.sort(key=lambda x: (prio_order.get(x["priority"], 9), x["title"] or ""))
            return {"backlog": snapshots[:limit]}

        if name == "get_team_capacity":
            sprint_days = int(args.get("sprint_duration_days") or 10)
            ctx = args.get("_context") or {}
            team = ctx.get("team_members") or []
            if team:
                per_person = 8
                total_capacity = len(team) * per_person
                buffer = int(total_capacity * 0.15)
                return {
                    "project_id": project_id,
                    "sprint_duration_days": sprint_days,
                    "member_count": len(team),
                    "total_capacity_points": total_capacity,
                    "buffer_points": buffer,
                    "available_points": max(0, total_capacity - buffer),
                }
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

        return super().execute_tool(name, args)

    def run(self, user_input: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = dict(context or {})
        project_id = str(ctx.get("project_id") or "default")
        ctx["tool_get_backlog"] = self.execute_tool("get_backlog", {"project_id": project_id, "limit": 50})
        cap_args = {"project_id": project_id, "sprint_duration_days": 10, "_context": ctx}
        ctx["tool_capacity"] = self.execute_tool("get_team_capacity", cap_args)
        return super().run(user_input, ctx)


def _dry_planning_payload(stories: list[TaskDict]) -> dict[str, Any]:
    points_cycle = (2, 3, 5, 3, 2)
    selected = []
    for i, t in enumerate(stories):
        if not t.get("id"):
            continue
        selected.append(
            {
                "task_id": t["id"],
                "title": t.get("title"),
                "priority": t.get("priority") or "P3",
                "estimated_points": points_cycle[i % len(points_cycle)],
                "reason_included": "dry_run: included all backlog items",
            }
        )
    return {
        "action": "plan_sprint",
        "sprint": {
            "name": "Sprint 1 (dry-run)",
            "goal": "Deliver the backlog slice with a working increment.",
            "start_date": None,
            "end_date": None,
            "total_capacity_points": 40,
            "planned_points": sum(r["estimated_points"] for r in selected),
            "buffer_points": 6,
        },
        "selected_tasks": selected,
        "excluded_tasks": [],
        "tasks_to_split": [],
        "warnings": ["dry_run: no API call"],
    }


def planning_node(state: AgentState) -> dict[str, Any]:
    stories = state.get("backlog") or []
    if not stories:
        return {"error": "Planning needs a non-empty backlog in state."}

    project_id = state.get("project_id") or "default"
    if is_llm_dry_run():
        data = _dry_planning_payload(stories)
    else:
        agent = PlanningAgent()
        compact = [
            {
                "id": t.get("id"),
                "title": t.get("title"),
                "description": t.get("description"),
                "priority": t.get("priority"),
            }
            for t in stories
        ]
        ctx = {
            "project_id": project_id,
            "backlog_from_state": compact,
            "team_members": state.get("team_members"),
        }
        hint = state.get("user_input") or "Plan the next sprint from the backlog in Context."
        out = agent.run(hint, ctx)
        if err := out.get("llm_error"):
            return {"error": err}
        raw = out.get("raw_output") or ""
        try:
            data = parse_json_blob(raw)
        except json.JSONDecodeError as e:
            return {"error": f"Planning agent returned invalid JSON: {e}"}

    selected = data.get("selected_tasks") if isinstance(data, dict) else None
    if not selected:
        return {"error": "Planning agent produced no selected_tasks."}

    by_id = {t["id"]: dict(t) for t in stories if t.get("id")}
    by_title = {t.get("title", "").lower(): dict(t) for t in stories if t.get("title")}

    sprint_plan: list[TaskDict] = []
    unmatched: list[dict[str, Any]] = []
    for row in selected:
        tid = row.get("task_id")
        base = None
        if tid and tid in by_id:
            base = by_id[tid]
        else:
            title = str(row.get("title") or "").lower()
            base = by_title.get(title)
        if not base:
            unmatched.append(dict(row))
            continue
        merged = dict(base)
        merged["story_points"] = int(row.get("estimated_points") or 1)
        sprint_plan.append(merged)

    if not sprint_plan:
        return {"error": "Planning could not match any selected_tasks to backlog items in state."}

    sprint_block = data.get("sprint") if isinstance(data.get("sprint"), dict) else {}
    goal = sprint_block.get("goal") if isinstance(sprint_block, dict) else None
    planning_extra = {
        "excluded_tasks": data.get("excluded_tasks") if isinstance(data, dict) else [],
        "tasks_to_split": data.get("tasks_to_split") if isinstance(data, dict) else [],
        "warnings": list(data.get("warnings") or []) if isinstance(data, dict) else [],
        "sprint": sprint_block,
        "unmatched_selected": unmatched,
    }
    save_sprint_plan(sprint_plan, project_id=project_id, goal=goal, meta=planning_extra)
    return {
        "sprint_plan": sprint_plan,
        "sprint_goal": goal,
        "planning_extra": planning_extra,
        "error": None,
    }
