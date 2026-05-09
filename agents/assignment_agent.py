"""
Assignment Agent — assigns work and suggests reviewers / next actions.

- Checks workload per team member (from DB + sprint context)
- Assigns tasks based on skills + availability
- Suggests reviewers
- Recommends next actions per user
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select

from agents.base import BaseAgent
from config import is_llm_dry_run
from db.models import TaskRow
from db.persist import save_assignments
from db.session import session_scope
from graph.state import AgentState, TaskDict
from llm.json_util import parse_json_blob


class AssignmentAgent(BaseAgent):
    name = "assignment_agent"
    description = "Assigns tasks to team members based on skills, workload, and availability."

    def system_prompt(self) -> str:
        return """
You are the Assignment Agent for AgileAI, an AI-powered agile project management system.

Your responsibilities:
1. Analyze team member workloads (tasks and story points already assigned in this project).
2. Match task requirements to team member skills from Context.
3. Assign exactly one primary assignee per task.
4. Suggest a reviewer (different from assignee, with relevant skills).
5. Recommend the next task each user should pick up.

Assignment logic:
- Avoid assigning to members at or over capacity (>= 8 points in workload snapshot unless Context says otherwise).
- Prefer skill fit, then lower load.
- Reviewer must differ from assignee when possible.

Return ONLY valid JSON (no markdown), exactly:
{
  "action": "assign",
  "assignments": [
    {
      "task_id": "...",
      "task_title": "...",
      "assigned_to": {"user_id": "...", "name": "...", "reason": "..."},
      "reviewer": {"user_id": "...", "name": "...", "reason": "..."}
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
  "warnings": []
}
Cover every sprint task id from Context.
"""

    def tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "get_team_workload",
                "description": "Story point load per member for active-ish tasks in the project.",
                "parameters": {
                    "type": "object",
                    "properties": {"project_id": {"type": "string"}},
                    "required": ["project_id"],
                },
            },
            {
                "name": "get_skill_matrix",
                "description": "Skills per member; uses Context.team_members.",
                "parameters": {
                    "type": "object",
                    "properties": {"project_id": {"type": "string"}},
                    "required": ["project_id"],
                },
            },
            {
                "name": "get_task_details",
                "description": "Full task row for assignment decisions.",
                "parameters": {
                    "type": "object",
                    "properties": {"task_id": {"type": "string"}},
                    "required": ["task_id"],
                },
            },
        ]

    def execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name == "get_team_workload":
            project_id = str(args["project_id"])
            ctx = args.get("_context") or {}
            active_statuses = ("backlog", "todo", "in_progress")
            with session_scope() as s:
                stmt = select(TaskRow).where(TaskRow.project_id == project_id).limit(2000)
                rows = list(s.scalars(stmt).all())
            by_member: dict[str, list[str]] = {}
            points_by_member: dict[str, int] = {}
            for t in rows:
                if t.status not in active_statuses or not t.assignee_id:
                    continue
                aid = t.assignee_id
                by_member.setdefault(aid, []).append(t.id)
                points_by_member[aid] = points_by_member.get(aid, 0) + int(t.story_points or 0)
            members_meta = {m["id"]: m for m in (ctx.get("team_members") or [])}
            workload = []
            for mid, meta in members_meta.items():
                pts = points_by_member.get(mid, 0) + int(meta.get("current_load") or 0)
                cap = 8
                workload.append(
                    {
                        "user_id": mid,
                        "name": meta.get("name"),
                        "assigned_points": pts,
                        "capacity_points": cap,
                        "available_points": max(0, cap - pts),
                        "task_count": len(by_member.get(mid, [])),
                    }
                )
            return {"workload": workload}

        if name == "get_skill_matrix":
            ctx = args.get("_context") or {}
            matrix = []
            for m in ctx.get("team_members") or []:
                skills = m.get("skills") or []
                matrix.append(
                    {
                        "user_id": m["id"],
                        "name": m.get("name"),
                        "skills": [{"skill": s, "level": 3} for s in skills],
                    }
                )
            return {"skill_matrix": matrix}

        if name == "get_task_details":
            tid = str(args["task_id"])
            with session_scope() as s:
                t = s.get(TaskRow, tid)
            if not t:
                return {"error": "Task not found"}
            return {
                "task_id": t.id,
                "title": t.title,
                "description": t.description,
                "labels": t.labels or [],
                "priority": t.priority,
                "story_points": t.story_points,
                "estimated_hours": t.estimated_hours,
            }

        return super().execute_tool(name, args)

    def run(self, user_input: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = dict(context or {})
        project_id = str(ctx.get("project_id") or "default")
        ctx["tool_workload"] = self.execute_tool(
            "get_team_workload", {"project_id": project_id, "_context": ctx}
        )
        ctx["tool_skills"] = self.execute_tool(
            "get_skill_matrix", {"project_id": project_id, "_context": ctx}
        )
        return super().run(user_input, ctx)


def _dry_assignment_json(sprint: list[TaskDict], team: list[dict[str, Any]]) -> dict[str, Any]:
    if not team:
        return {"action": "assign", "assignments": [], "next_actions": [], "warnings": ["dry_run: no team"]}
    assignments = []
    next_actions = []
    for i, t in enumerate(sprint):
        tid = t.get("id")
        if not tid:
            continue
        assignee = team[i % len(team)]
        reviewer = team[(i + 1) % len(team)]
        assignments.append(
            {
                "task_id": tid,
                "task_title": t.get("title"),
                "assigned_to": {
                    "user_id": assignee["id"],
                    "name": assignee.get("name", ""),
                    "reason": "dry_run: round-robin by order",
                },
                "reviewer": {
                    "user_id": reviewer["id"],
                    "name": reviewer.get("name", ""),
                    "reason": "dry_run: next teammate reviews",
                },
            }
        )
        next_actions.append(
            {
                "user_id": assignee["id"],
                "recommended_task_id": tid,
                "recommended_task_title": t.get("title", ""),
                "reason": "dry_run: your assigned sprint task",
            }
        )
    return {
        "action": "assign",
        "assignments": assignments,
        "next_actions": next_actions,
        "warnings": ["dry_run: no API call"],
    }


def assignment_node(state: AgentState) -> dict[str, Any]:
    sprint = state.get("sprint_plan") or []
    team = state.get("team_members") or []
    if not sprint:
        return {"error": "Assignment needs sprint_plan in state."}
    if not team:
        return {"error": "Assignment needs team_members in state."}

    project_id = state.get("project_id") or "default"
    if is_llm_dry_run():
        data = _dry_assignment_json(sprint, team)
    else:
        agent = AssignmentAgent()
        ctx = {
            "project_id": project_id,
            "sprint_plan": sprint,
            "team_members": team,
        }
        hint = state.get("user_input") or "Assign sprint tasks to the team with reviewers."
        out = agent.run(hint, ctx)
        if err := out.get("llm_error"):
            return {"error": err}
        raw = out.get("raw_output") or ""
        try:
            data = parse_json_blob(raw)
        except json.JSONDecodeError as e:
            return {"error": f"Assignment agent returned invalid JSON: {e}"}

    rows = data.get("assignments") if isinstance(data, dict) else None
    if not rows:
        return {"error": "Assignment agent produced no assignments."}

    by_task = {t["id"]: dict(t) for t in sprint if t.get("id")}
    for row in rows:
        tid = row.get("task_id")
        assignee = row.get("assigned_to") or {}
        reviewer = row.get("reviewer") or {}
        uid = assignee.get("user_id")
        rid = reviewer.get("user_id")
        if tid and tid in by_task and uid:
            by_task[tid]["assignee_id"] = str(uid)
            if rid:
                by_task[tid]["reviewer_id"] = str(rid)

    assignments: list[TaskDict] = list(by_task.values())
    extra = {
        "next_actions": data.get("next_actions") if isinstance(data, dict) else [],
        "warnings": data.get("warnings") if isinstance(data, dict) else [],
        "action": data.get("action") if isinstance(data, dict) else None,
    }
    save_assignments(assignments)
    return {"assignments": assignments, "assignment_extra": extra, "error": None}
