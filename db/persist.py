import uuid
from typing import Any
from sqlalchemy import select, func
from db.models import AssignmentRow, ProjectRow, SprintPlanRow, TaskRow, UserRow, MemberSkillRow
from db.session import session_scope
from graph.state import TaskDict

def map_priority(p: str | None) -> str:
    """Map standard priority to Prisma Priority enum values."""
    if not p:
        return "P3_MEDIUM"
    p_upper = p.strip().upper()
    if p_upper in ("P1", "P1_CRITICAL", "CRITICAL"):
        return "P1_CRITICAL"
    if p_upper in ("P2", "P2_HIGH", "HIGH"):
        return "P2_HIGH"
    if p_upper in ("P3", "P3_MEDIUM", "MEDIUM"):
        return "P3_MEDIUM"
    if p_upper in ("P4", "P4_LOW", "LOW"):
        return "P4_LOW"
    return "P3_MEDIUM"

def ensure_project(project_id: str, *, name: str | None = None) -> None:
    with session_scope() as s:
        row = s.get(ProjectRow, project_id)
        if row is None:
            s.add(
                ProjectRow(
                    id=project_id,
                    key=project_id.upper()[:10],
                    name=name or project_id
                )
            )

def ensure_users(users: list[dict[str, Any]]) -> None:
    with session_scope() as s:
        for u in users:
            uid = str(u.get("id") or u.get("user_id") or "")
            if not uid:
                continue
            
            # 1. Ensure User row exists
            existing = s.get(UserRow, uid)
            if existing is None:
                existing = UserRow(
                    id=uid,
                    name=str(u.get("name") or uid),
                    email=str(u.get("email") or f"{uid}@example.com"),
                    avatar=u.get("avatar"),
                )
                s.add(existing)
            else:
                if u.get("name"):
                    existing.name = str(u["name"])
                if u.get("email"):
                    existing.email = str(u["email"])
                if u.get("avatar"):
                    existing.avatar = str(u["avatar"])

            # 2. Write Skills to MemberSkill table if passed
            skills = u.get("skills")
            if isinstance(skills, list):
                for skill_name in skills:
                    # Check if User already has this skill
                    stmt = select(MemberSkillRow).where(
                        MemberSkillRow.userId == uid,
                        MemberSkillRow.skill == skill_name
                    )
                    skill_row = s.scalars(stmt).first()
                    if skill_row is None:
                        s.add(
                            MemberSkillRow(
                                id=str(uuid.uuid4()),
                                userId=uid,
                                skill=skill_name,
                                level=3
                            )
                        )

def save_backlog(tasks: list[TaskDict], *, default_project_id: str = "default") -> None:
    with session_scope() as s:
        for index, t in enumerate(tasks):
            pid = t.get("project_id") or default_project_id
            
            # Ensure Project exists
            proj = s.get(ProjectRow, pid)
            if proj is None:
                proj = ProjectRow(id=pid, key=pid.upper()[:10], name=pid)
                s.add(proj)
            
            project_key = proj.key or pid.upper()[:10]

            # Generate task key (e.g. "PROJ-12")
            existing_count = s.scalar(
                select(func.count()).select_from(TaskRow).where(TaskRow.projectId == pid)
            ) or 0
            task_num = existing_count + index + 1
            task_key = f"{project_key}-{task_num}"

            # reporterId and creatorId are required in Prisma
            reporter = t.get("reporter_id") or "system"
            creator = t.get("creator_id") or "system"

            row = TaskRow(
                id=t.get("id") or str(uuid.uuid4()),
                projectId=pid,
                title=t.get("title", ""),
                description=t.get("description", ""),
                acceptanceCriteria=t.get("acceptance_criteria"),
                storyPoints=t.get("story_points"),
                status=(t.get("status") or "BACKLOG").upper(),
                type=(t.get("type") or "TASK").upper(),
                priority=map_priority(t.get("priority")),
                labels=t.get("labels") or [],
                estimatedHours=float(t.get("estimated_hours")) if t.get("estimated_hours") is not None else None,
                assigneeId=t.get("assignee_id"),
                reviewerId=t.get("reviewer_id"),
                aiGenerated=bool(t.get("ai_generated", True)),
                reporterId=reporter,
                creatorId=creator,
                key=t.get("key") or task_key,
                sprintPlanId=t.get("sprint_plan_id")
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
        # Ensure project exists
        proj = s.get(ProjectRow, project_id)
        if proj is None:
            proj = ProjectRow(id=project_id, key=project_id.upper()[:10], name=project_id)
            s.add(proj)

        sprint_block = (meta or {}).get("sprint") or {}
        plan_id = str(uuid.uuid4())
        
        # In Prisma, SprintPlan has:
        # id, projectId, name, goal, status, color, creatorId, totalCapacityPoints, plannedPoints, bufferPoints
        plan = SprintPlanRow(
            id=plan_id,
            projectId=project_id,
            goal=goal or sprint_block.get("goal") or "",
            name=sprint_block.get("name") or "Sprint 1",
            status="DRAFT",
            color=sprint_block.get("color") or "#0052CC",
            creatorId="system",
            totalCapacityPoints=int(sprint_block.get("total_capacity_points") or 0),
            plannedPoints=int(sprint_block.get("planned_points") or 0),
            bufferPoints=int(sprint_block.get("buffer_points") or 0),
        )
        s.add(plan)
        
        # Link tasks to this sprint
        for t in ordered_tasks:
            tid = t.get("id")
            if not tid:
                continue
            row = s.get(TaskRow, tid)
            if row is not None:
                row.sprintPlanId = plan_id
                row.storyPoints = t.get("story_points")

def save_assignments(tasks_with_assignees: list[TaskDict]) -> None:
    with session_scope() as s:
        for t in tasks_with_assignees:
            tid = t.get("id")
            aid = t.get("assignee_id")
            rid = t.get("reviewer_id")
            pid = t.get("project_id") or "default"
            if not tid or not aid:
                continue
            
            # Ensure users exist
            if s.get(UserRow, aid) is None:
                s.add(UserRow(id=aid, name=aid, email=f"{aid}@example.com"))
            if rid and s.get(UserRow, rid) is None:
                s.add(UserRow(id=rid, name=rid, email=f"{rid}@example.com"))
            
            # Create Assignment
            s.add(
                AssignmentRow(
                    id=str(uuid.uuid4()),
                    taskId=tid,
                    projectId=pid,
                    assigneeId=aid,
                    reviewerId=rid,
                    applied=True,
                )
            )
            
            # Update Task assignees
            row = s.get(TaskRow, tid)
            if row is not None:
                row.assigneeId = aid
                if rid:
                    row.reviewerId = rid
