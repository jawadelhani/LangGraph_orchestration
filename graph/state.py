"""Shared graph state — single source of truth passed between nodes."""
from typing import Any, Literal, NotRequired, Optional, TypedDict


class TaskDict(TypedDict, total=False):
    id: str
    project_id: str
    title: str
    description: str
    acceptance_criteria: list[str]
    story_points: Optional[int]
    status: str
    priority: Optional[str]
    labels: list[str]
    estimated_hours: Optional[int]
    assignee_id: Optional[str]
    reviewer_id: Optional[str]
    ai_generated: bool


class TeamMemberDict(TypedDict):
    id: str
    name: str
    skills: list[str]
    current_load: int


class AgentState(TypedDict, total=False):
    user_input: str
    project_id: str
    next_agent: NotRequired[Literal["task", "planning", "assignment"] | str]
    backlog: list[TaskDict]
    sprint_plan: list[TaskDict]
    assignments: list[TaskDict]
    team_members: list[TeamMemberDict]
    sprint_goal: NotRequired[Optional[str]]
    planning_extra: NotRequired[dict[str, Any] | None]
    assignment_extra: NotRequired[dict[str, Any] | None]
    skip_db_write: NotRequired[bool]
    error: Optional[str]
