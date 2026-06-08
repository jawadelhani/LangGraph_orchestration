from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Float
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class Base(DeclarativeBase):
    pass

class ProjectRow(Base):
    __tablename__ = "Project"
    __table_args__ = {"schema": "business"}

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    imageUrl: Mapped[str | None] = mapped_column(String(512), nullable=True)
    defaultAssignee: Mapped[str | None] = mapped_column(String(64), nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updatedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, onupdate=utcnow)
    deletedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class UserRow(Base):
    __tablename__ = "User"
    __table_args__ = {"schema": "business"}

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    email: Mapped[str] = mapped_column(String(256), unique=True)
    avatar: Mapped[str | None] = mapped_column(String(512), nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updatedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    deletedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class MemberSkillRow(Base):
    __tablename__ = "MemberSkill"
    __table_args__ = {"schema": "business"}

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    userId: Mapped[str] = mapped_column(String(64), ForeignKey("business.User.id", ondelete="CASCADE"), index=True)
    skill: Mapped[str] = mapped_column(String(256))
    level: Mapped[int] = mapped_column(Integer, default=3)
    updatedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class SprintPlanRow(Base):
    __tablename__ = "SprintPlan"
    __table_args__ = {"schema": "agents"}

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    projectId: Mapped[str] = mapped_column(String(64), index=True)
    validationId: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(256))
    goal: Mapped[str] = mapped_column(Text, default="")
    startDate: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    endDate: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT") # DRAFT, VALIDATED, ACTIVE, CLOSED
    color: Mapped[str] = mapped_column(String(64), default="#0052CC")
    creatorId: Mapped[str] = mapped_column(String(64), index=True)
    totalCapacityPoints: Mapped[int] = mapped_column(Integer, default=0)
    plannedPoints: Mapped[int] = mapped_column(Integer, default=0)
    bufferPoints: Mapped[int] = mapped_column(Integer, default=0)
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updatedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    deletedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class TaskRow(Base):
    __tablename__ = "Task"
    __table_args__ = {"schema": "agents"}

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    projectId: Mapped[str] = mapped_column(String(64), index=True)
    sprintPlanId: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    assigneeId: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewerId: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reporterId: Mapped[str] = mapped_column(String(64))
    creatorId: Mapped[str] = mapped_column(String(64), index=True)
    parentTaskId: Mapped[str | None] = mapped_column(String(64), nullable=True)
    validationId: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    acceptanceCriteria: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="BACKLOG") # BACKLOG, TODO, IN_PROGRESS, IN_REVIEW, DONE
    type: Mapped[str] = mapped_column(String(32), default="TASK") # BUG, TASK, SUBTASK, STORY, EPIC
    priority: Mapped[str] = mapped_column(String(32), default="P3_MEDIUM") # P1_CRITICAL, P2_HIGH, P3_MEDIUM, P4_LOW
    labels: Mapped[list | None] = mapped_column(ARRAY(String), nullable=True)
    storyPoints: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimatedHours: Mapped[float | None] = mapped_column(Float, nullable=True)
    sprintPosition: Mapped[float] = mapped_column(Float, default=0.0)
    boardPosition: Mapped[float] = mapped_column(Float, default=-1.0)
    sprintColor: Mapped[str | None] = mapped_column(String(64), nullable=True)
    deletedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    isBlocked: Mapped[bool] = mapped_column(Boolean, default=False)
    blockedReason: Mapped[str | None] = mapped_column(Text, nullable=True)
    aiGenerated: Mapped[bool] = mapped_column(Boolean, default=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updatedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    key: Mapped[str] = mapped_column(String(64))

class AssignmentRow(Base):
    __tablename__ = "Assignment"
    __table_args__ = {"schema": "agents"}

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    taskId: Mapped[str] = mapped_column(String(64), index=True)
    projectId: Mapped[str] = mapped_column(String(64), index=True)
    validationId: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assigneeId: Mapped[str] = mapped_column(String(64))
    reviewerId: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assigneeReason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewerReason: Mapped[str | None] = mapped_column(Text, nullable=True)
    workloadSnapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    applied: Mapped[bool] = mapped_column(Boolean, default=False)
    appliedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
