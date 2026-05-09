import uuid
from typing import Any

from db.models import AssignmentRow, SprintPlanRow, TaskRow
from db.session import session_scope
from graph.state import TaskDict


def save_backlog(tasks: list[TaskDict], *, default_project_id: str = "default") -> None:
    with session_scope() as s:
        for t in tasks:
            pid = t.get("project_id") or default_project_id
            row = TaskRow(
                id=t.get("id") or str(uuid.uuid4()),
                project_id=pid,
                title=t.get("title", ""),
                description=t.get("description", ""),
                acceptance_criteria=t.get("acceptance_criteria"),
                story_points=t.get("story_points"),
                status=t.get("status") or "backlog",
                priority=t.get("priority"),
                labels=t.get("labels"),
                estimated_hours=t.get("estimated_hours"),
                assignee_id=t.get("assignee_id"),
                reviewer_id=t.get("reviewer_id"),
                ai_generated=bool(t.get("ai_generated", True)),
            )
            s.merge(row)


def save_sprint_plan(
    ordered_tasks: list[TaskDict],
    *,
    project_id: str = "default",
    goal: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    with session_scope() as s:
        ids = [t["id"] for t in ordered_tasks if t.get("id")]
        plan = SprintPlanRow(
            id=str(uuid.uuid4()),
            project_id=project_id,
            goal=goal,
            task_ids_ordered=ids,
            meta=meta or None,
        )
        s.add(plan)
        for t in ordered_tasks:
            tid = t.get("id")
            if not tid:
                continue
            row = s.get(TaskRow, tid)
            if row is not None:
                row.story_points = t.get("story_points")


def save_assignments(tasks_with_assignees: list[TaskDict]) -> None:
    with session_scope() as s:
        for t in tasks_with_assignees:
            tid = t.get("id")
            aid = t.get("assignee_id")
            rid = t.get("reviewer_id")
            if not tid or not aid:
                continue
            s.add(
                AssignmentRow(
                    id=str(uuid.uuid4()),
                    task_id=tid,
                    assignee_id=aid,
                    reviewer_id=rid,
                )
            )
            row = s.get(TaskRow, tid)
            if row is not None:
                row.assignee_id = aid
                if rid:
                    row.reviewer_id = rid
