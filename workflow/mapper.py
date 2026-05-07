"""
DB Mapper
Converts raw JSON output from AI agents into validated SQLAlchemy model instances.
Does NOT write to DB — returns model objects for human validation first.
"""

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Any

from models import Task, Sprint, SprintTask


# ─── Parsed output containers ─────────────────────────────────────────────────

@dataclass
class MappedTask:
    title: str
    description: str
    priority: str
    labels: list[str]
    estimated_hours: float | None
    story_points: int | None
    acceptance_criteria: list[str]
    duplicate_of: str | None
    split_from: str | None
    ai_generated: bool = True
    # populated later
    project_id: str | None = None
    assignee_id: str | None = None


@dataclass
class MappedAssignment:
    task_id: str
    task_title: str
    assignee_id: str
    assignee_name: str
    assignee_reason: str
    reviewer_id: str | None
    reviewer_name: str | None
    reviewer_reason: str | None


@dataclass
class MappedSprint:
    name: str
    goal: str
    start_date: str
    end_date: str
    total_capacity_points: int
    planned_points: int
    buffer_points: int
    selected_task_ids: list[str]
    tasks_to_split: list[dict]
    warnings: list[str]


@dataclass
class MapperResult:
    agent: str
    action: str
    mapped_tasks: list[MappedTask] = field(default_factory=list)
    mapped_assignments: list[MappedAssignment] = field(default_factory=list)
    mapped_sprint: MappedSprint | None = None
    warnings: list[str] = field(default_factory=list)
    raw_json: dict = field(default_factory=dict)


# ─── JSON extractor ───────────────────────────────────────────────────────────

def extract_json(raw_output: str) -> dict:
    """
    Extract JSON from agent raw_output.
    Gemini sometimes wraps JSON in markdown code fences — strip them.
    """
    # Try direct parse first
    try:
        return json.loads(raw_output)
    except json.JSONDecodeError:
        pass

    # Strip ```json ... ``` fences
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw_output)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Find first { ... } block
    match = re.search(r"\{[\s\S]+\}", raw_output)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract valid JSON from agent output:\n{raw_output[:500]}")


# ─── Priority validator ───────────────────────────────────────────────────────

VALID_PRIORITIES = {"P1", "P2", "P3", "P4"}
VALID_STORY_POINTS = {1, 2, 3, 5, 8, 13}


def validate_priority(p: str) -> str:
    if p in VALID_PRIORITIES:
        return p
    return "P3"  # safe default


def validate_story_points(sp: int | None) -> int | None:
    if sp is None:
        return None
    # Round to nearest Fibonacci
    closest = min(VALID_STORY_POINTS, key=lambda x: abs(x - sp))
    return closest


# ─── Agent-specific mappers ───────────────────────────────────────────────────

def map_task_agent_output(raw_output: str, project_id: str) -> MapperResult:
    data = extract_json(raw_output)
    result = MapperResult(agent="task_agent", action=data.get("action", "create"), raw_json=data)

    for t in data.get("tasks", []):
        mapped = MappedTask(
            title=str(t.get("title", "Untitled Task")).strip(),
            description=str(t.get("description", "")).strip(),
            priority=validate_priority(t.get("priority", "P3")),
            labels=[str(l).lower() for l in t.get("labels", [])],
            estimated_hours=float(t["estimated_hours"]) if t.get("estimated_hours") is not None else None,
            story_points=validate_story_points(t.get("story_points")),
            acceptance_criteria=[str(c) for c in t.get("acceptance_criteria", [])],
            duplicate_of=t.get("duplicate_of"),
            split_from=t.get("split_from"),
            project_id=project_id,
        )
        result.mapped_tasks.append(mapped)

    result.warnings = [str(w) for w in data.get("warnings", [])]
    return result


def map_assignment_agent_output(raw_output: str) -> MapperResult:
    data = extract_json(raw_output)
    result = MapperResult(agent="assignment_agent", action=data.get("action", "assign"), raw_json=data)

    for a in data.get("assignments", []):
        assigned = a.get("assigned_to", {})
        reviewer = a.get("reviewer", {})
        mapped = MappedAssignment(
            task_id=str(a.get("task_id", "")),
            task_title=str(a.get("task_title", "")),
            assignee_id=str(assigned.get("user_id", "")),
            assignee_name=str(assigned.get("name", "")),
            assignee_reason=str(assigned.get("reason", "")),
            reviewer_id=str(reviewer.get("user_id")) if reviewer.get("user_id") else None,
            reviewer_name=str(reviewer.get("name")) if reviewer.get("name") else None,
            reviewer_reason=str(reviewer.get("reason")) if reviewer.get("reason") else None,
        )
        result.mapped_assignments.append(mapped)

    result.warnings = [str(w) for w in data.get("warnings", [])]
    return result


def map_planning_agent_output(raw_output: str) -> MapperResult:
    data = extract_json(raw_output)
    result = MapperResult(agent="planning_agent", action=data.get("action", "plan_sprint"), raw_json=data)

    sprint_data = data.get("sprint", {})
    selected = data.get("selected_tasks", [])

    result.mapped_sprint = MappedSprint(
        name=str(sprint_data.get("name", "New Sprint")),
        goal=str(sprint_data.get("goal", "")),
        start_date=str(sprint_data.get("start_date", "")),
        end_date=str(sprint_data.get("end_date", "")),
        total_capacity_points=int(sprint_data.get("total_capacity_points", 0)),
        planned_points=int(sprint_data.get("planned_points", 0)),
        buffer_points=int(sprint_data.get("buffer_points", 0)),
        selected_task_ids=[str(t["task_id"]) for t in selected if t.get("task_id")],
        tasks_to_split=data.get("tasks_to_split", []),
        warnings=data.get("warnings", []),
    )

    result.warnings = [str(w) for w in data.get("warnings", [])]
    return result


# ─── Universal mapper entry point ─────────────────────────────────────────────

def map_agent_output(agent_name: str, raw_output: str, context: dict = {}) -> MapperResult:
    """
    Entry point: given agent name + raw LLM output, return a MapperResult.
    Raises ValueError if JSON extraction fails.
    """
    project_id = context.get("project_id", "")

    if agent_name == "task_agent":
        return map_task_agent_output(raw_output, project_id)
    elif agent_name == "assignment_agent":
        return map_assignment_agent_output(raw_output)
    elif agent_name == "planning_agent":
        return map_planning_agent_output(raw_output)
    else:
        raise ValueError(f"Unknown agent: {agent_name}")


# ─── DB writers (called AFTER human validation) ───────────────────────────────

def write_tasks_to_db(mapped_tasks: list[MappedTask], db) -> list[Task]:
    """Write validated MappedTask objects to the DB. Returns created Task ORM instances."""
    created = []
    for mt in mapped_tasks:
        if mt.duplicate_of:
            # Skip confirmed duplicates
            continue
        task = Task(
            id=str(uuid.uuid4()),
            project_id=mt.project_id,
            title=mt.title,
            description=mt.description,
            priority=mt.priority,
            labels=mt.labels,
            estimated_hours=mt.estimated_hours,
            story_points=mt.story_points,
            acceptance_criteria=mt.acceptance_criteria,
            assignee_id=mt.assignee_id,
            status="backlog",
            ai_generated=mt.ai_generated,
            created_at=datetime.utcnow(),
        )
        db.add(task)
        created.append(task)
    db.commit()
    return created


def write_assignments_to_db(mapped_assignments: list[MappedAssignment], db) -> list[Task]:
    """Update assignee_id on existing tasks. Returns updated Task instances."""
    updated = []
    for ma in mapped_assignments:
        task = db.query(Task).filter(Task.id == ma.task_id).first()
        if task:
            task.assignee_id = ma.assignee_id
            task.reviewer_id = ma.reviewer_id
            updated.append(task)
    db.commit()
    return updated


def write_sprint_to_db(mapped_sprint: MappedSprint, project_id: str, db) -> Sprint:
    """Create a Sprint and link selected tasks. Returns created Sprint instance."""
    sprint = Sprint(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name=mapped_sprint.name,
        goal=mapped_sprint.goal,
        start_date=mapped_sprint.start_date,
        end_date=mapped_sprint.end_date,
        status="planned",
        created_at=datetime.utcnow(),
    )
    db.add(sprint)
    db.flush()  # get sprint.id before linking tasks

    for task_id in mapped_sprint.selected_task_ids:
        link = SprintTask(sprint_id=sprint.id, task_id=task_id, added_by="planning_agent")
        db.add(link)
        # Update task sprint_id
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.sprint_id = sprint.id

    db.commit()
    return sprint
