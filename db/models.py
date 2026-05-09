from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class TaskRow(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(Text, default="")
    acceptance_criteria: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    story_points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="backlog")
    priority: Mapped[str | None] = mapped_column(String(8), nullable=True)
    labels: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    estimated_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assignee_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SprintPlanRow(Base):
    __tablename__ = "sprint_plans"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_ids_ordered: Mapped[list] = mapped_column(JSONB)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AssignmentRow(Base):
    __tablename__ = "assignments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), index=True)
    assignee_id: Mapped[str] = mapped_column(String(64))
    reviewer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VelocityHistoryRow(Base):
    __tablename__ = "velocity_history"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    sprint_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    planned_points: Mapped[int] = mapped_column(Integer, default=0)
    completed_points: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
