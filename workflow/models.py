"""
models.py — SQLAlchemy ORM models (Agent DB + User DB)
Referenced by agents, mapper, and validation layer.
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime,
    ForeignKey, Text, JSON, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import DeclarativeBase
import enum


class Base(DeclarativeBase):
    pass


# ─── Enums ────────────────────────────────────────────────────────────────────

class ValidationStatus:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"


# ─── Agent DB Models ──────────────────────────────────────────────────────────

class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, nullable=False, index=True)
    sprint_id = Column(String, ForeignKey("sprints.id"), nullable=True, index=True)
    assignee_id = Column(String, nullable=True)
    reviewer_id = Column(String, nullable=True)

    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(String(2), default="P3")          # P1, P2, P3, P4
    status = Column(String(50), default="backlog")       # backlog, todo, in_progress, done
    labels = Column(JSON, default=list)
    estimated_hours = Column(Float, nullable=True)
    story_points = Column(Integer, nullable=True)
    acceptance_criteria = Column(JSON, default=list)

    ai_generated = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Sprint(Base):
    __tablename__ = "sprints"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    goal = Column(Text, nullable=True)
    start_date = Column(String(20), nullable=True)
    end_date = Column(String(20), nullable=True)
    status = Column(String(50), default="planned")      # planned, active, completed
    velocity = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SprintTask(Base):
    __tablename__ = "sprint_tasks"

    sprint_id = Column(String, ForeignKey("sprints.id"), primary_key=True)
    task_id = Column(String, ForeignKey("tasks.id"), primary_key=True)
    added_by = Column(String(50), default="human")      # human | planning_agent


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_name = Column(String(100), nullable=False, index=True)
    input = Column(Text, nullable=True)
    output = Column(Text, nullable=True)
    tools_called = Column(JSON, default=list)
    duration_ms = Column(Integer, nullable=True)
    context = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class ValidationRequest(Base):
    __tablename__ = "validation_requests"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_name = Column(String(100), nullable=False)
    action = Column(String(100), nullable=True)
    status = Column(String(50), default=ValidationStatus.PENDING, index=True)
    project_id = Column(String, nullable=False, index=True)
    requested_by = Column(String, nullable=True)
    payload = Column(Text, nullable=True)           # JSON string
    warnings = Column(Text, default="[]")           # JSON string
    raw_json = Column(Text, nullable=True)          # JSON string
    decision_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    decided_at = Column(DateTime, nullable=True)


class VelocityHistory(Base):
    __tablename__ = "velocity_history"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, nullable=False, index=True)
    sprint_id = Column(String, ForeignKey("sprints.id"), nullable=True)
    planned_points = Column(Integer, default=0)
    completed_points = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


# ─── User DB Models ───────────────────────────────────────────────────────────

class TeamMember(Base):
    __tablename__ = "team_members"

    user_id = Column(String, primary_key=True)
    project_id = Column(String, primary_key=True)
    name = Column(String(200), nullable=False)
    email = Column(String(300), nullable=True)
    role = Column(String(100), default="developer")
    avatar_url = Column(String(500), nullable=True)


class Skill(Base):
    __tablename__ = "skills"

    user_id = Column(String, ForeignKey("team_members.user_id"), primary_key=True)
    skill_name = Column(String(100), primary_key=True)
    level = Column(Integer, default=3)              # 1–5
