"""
Human Validation Layer
======================
Before any AI agent output is written to the database, it goes through this layer.

Flow:
  1. Agent runs → output mapped to structured objects (MapperResult)
  2. ValidationRequest created and stored (status = PENDING)
  3. Human reviews via API (GET /validations/{id})
  4. Human approves / rejects / edits (PATCH /validations/{id})
  5. On approval → DB writers called → data written
  6. On rejection → nothing written, reason logged

The validation store uses Redis for fast access during the review window,
with a fallback to PostgreSQL for persistence.
"""

import json
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from db import get_agent_db, get_redis
from mapper import (
    MapperResult,
    MappedTask,
    MappedAssignment,
    MappedSprint,
    write_tasks_to_db,
    write_assignments_to_db,
    write_sprint_to_db,
)
from models import ValidationRequest, ValidationStatus


# ─── Enums ────────────────────────────────────────────────────────────────────

class ValidationAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    EDIT_AND_APPROVE = "edit_and_approve"


# ─── Request/Response schemas ─────────────────────────────────────────────────

class ValidationResponse(BaseModel):
    validation_id: str
    agent: str
    action: str
    status: str
    created_at: str
    expires_at: str
    payload: dict          # the mapped data for human review
    warnings: list[str]


class ValidationDecision(BaseModel):
    action: ValidationAction
    reason: str | None = None
    # Optional: human can send back edited payload
    edited_tasks: list[dict] | None = None
    edited_assignments: list[dict] | None = None
    edited_sprint: dict | None = None


class ValidationResult(BaseModel):
    validation_id: str
    status: str
    message: str
    written_ids: list[str] = []


# ─── Validation Store ─────────────────────────────────────────────────────────

VALIDATION_TTL_SECONDS = 60 * 60 * 24  # 24 hours


def _validation_redis_key(validation_id: str) -> str:
    return f"validation:{validation_id}"


def store_validation(mapper_result: MapperResult, project_id: str, requested_by: str) -> str:
    """
    Stores a MapperResult as a pending ValidationRequest.
    Returns the validation_id.
    """
    validation_id = str(uuid.uuid4())
    now = datetime.utcnow()
    expires_at = now + timedelta(seconds=VALIDATION_TTL_SECONDS)

    payload = _mapper_result_to_payload(mapper_result)

    record = {
        "validation_id": validation_id,
        "agent": mapper_result.agent,
        "action": mapper_result.action,
        "status": ValidationStatus.PENDING,
        "project_id": project_id,
        "requested_by": requested_by,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "payload": payload,
        "warnings": mapper_result.warnings,
        "raw_json": mapper_result.raw_json,
    }

    # Store in Redis (fast, ephemeral)
    redis = get_redis()
    redis.setex(
        _validation_redis_key(validation_id),
        VALIDATION_TTL_SECONDS,
        json.dumps(record),
    )

    # Also persist to PostgreSQL for audit trail
    db = get_agent_db()
    try:
        db_record = ValidationRequest(
            id=validation_id,
            agent_name=mapper_result.agent,
            action=mapper_result.action,
            status=ValidationStatus.PENDING,
            project_id=project_id,
            requested_by=requested_by,
            payload=json.dumps(payload),
            warnings=json.dumps(mapper_result.warnings),
            raw_json=json.dumps(mapper_result.raw_json),
            created_at=now,
            expires_at=expires_at,
        )
        db.add(db_record)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[Validation] Failed to persist to DB: {e}")
    finally:
        db.close()

    return validation_id


def get_validation(validation_id: str) -> dict | None:
    """Retrieve a validation record by ID (checks Redis first, then DB)."""
    redis = get_redis()
    raw = redis.get(_validation_redis_key(validation_id))
    if raw:
        return json.loads(raw)

    # Fallback to DB
    db = get_agent_db()
    try:
        record = db.query(ValidationRequest).filter(ValidationRequest.id == validation_id).first()
        if record:
            return {
                "validation_id": str(record.id),
                "agent": record.agent_name,
                "action": record.action,
                "status": record.status,
                "project_id": record.project_id,
                "requested_by": record.requested_by,
                "created_at": record.created_at.isoformat(),
                "expires_at": record.expires_at.isoformat(),
                "payload": json.loads(record.payload),
                "warnings": json.loads(record.warnings),
                "raw_json": json.loads(record.raw_json),
            }
    finally:
        db.close()
    return None


def _update_validation_status(validation_id: str, status: str, reason: str | None = None):
    """Update status in both Redis and DB."""
    redis = get_redis()
    raw = redis.get(_validation_redis_key(validation_id))
    if raw:
        record = json.loads(raw)
        record["status"] = status
        record["decision_reason"] = reason
        record["decided_at"] = datetime.utcnow().isoformat()
        redis.setex(_validation_redis_key(validation_id), VALIDATION_TTL_SECONDS, json.dumps(record))

    db = get_agent_db()
    try:
        record = db.query(ValidationRequest).filter(ValidationRequest.id == validation_id).first()
        if record:
            record.status = status
            record.decision_reason = reason
            record.decided_at = datetime.utcnow()
            db.commit()
    except Exception as e:
        db.rollback()
    finally:
        db.close()


# ─── Decision handler ─────────────────────────────────────────────────────────

def process_decision(validation_id: str, decision: ValidationDecision) -> ValidationResult:
    """
    Core handler: approve / reject / edit-and-approve a validation request.
    """
    record = get_validation(validation_id)
    if not record:
        raise ValueError(f"Validation {validation_id} not found or expired.")

    if record["status"] != ValidationStatus.PENDING:
        raise ValueError(f"Validation {validation_id} already decided: {record['status']}")

    project_id = record["project_id"]
    agent = record["agent"]
    written_ids = []

    if decision.action == ValidationAction.REJECT:
        _update_validation_status(validation_id, ValidationStatus.REJECTED, decision.reason)
        return ValidationResult(
            validation_id=validation_id,
            status=ValidationStatus.REJECTED,
            message=f"Rejected. Reason: {decision.reason or 'none given'}",
        )

    # Approve or Edit-and-Approve
    payload = record["payload"]

    # If human edited the payload, merge their changes
    if decision.action == ValidationAction.EDIT_AND_APPROVE:
        if decision.edited_tasks:
            payload["tasks"] = decision.edited_tasks
        if decision.edited_assignments:
            payload["assignments"] = decision.edited_assignments
        if decision.edited_sprint:
            payload["sprint"] = decision.edited_sprint

    db = get_agent_db()
    try:
        if agent == "task_agent":
            tasks = [_dict_to_mapped_task(t, project_id) for t in payload.get("tasks", [])]
            created = write_tasks_to_db(tasks, db)
            written_ids = [t.id for t in created]

        elif agent == "assignment_agent":
            assignments = [_dict_to_mapped_assignment(a) for a in payload.get("assignments", [])]
            updated = write_assignments_to_db(assignments, db)
            written_ids = [t.id for t in updated]

        elif agent == "planning_agent":
            sprint_data = payload.get("sprint", {})
            mapped_sprint = _dict_to_mapped_sprint(sprint_data, payload.get("selected_task_ids", []))
            sprint = write_sprint_to_db(mapped_sprint, project_id, db)
            written_ids = [sprint.id]

        _update_validation_status(validation_id, ValidationStatus.APPROVED, decision.reason)
        return ValidationResult(
            validation_id=validation_id,
            status=ValidationStatus.APPROVED,
            message=f"Approved and written to database. {len(written_ids)} records created/updated.",
            written_ids=written_ids,
        )

    except Exception as e:
        db.rollback()
        _update_validation_status(validation_id, ValidationStatus.FAILED, str(e))
        raise
    finally:
        db.close()


# ─── FastAPI Router ───────────────────────────────────────────────────────────

router = APIRouter(prefix="/validations", tags=["Human Validation"])


@router.get("/{validation_id}", response_model=ValidationResponse)
def get_validation_endpoint(validation_id: str):
    """Get a pending validation for human review."""
    record = get_validation(validation_id)
    if not record:
        raise HTTPException(status_code=404, detail="Validation not found or expired.")
    return ValidationResponse(**{
        "validation_id": record["validation_id"],
        "agent": record["agent"],
        "action": record["action"],
        "status": record["status"],
        "created_at": record["created_at"],
        "expires_at": record["expires_at"],
        "payload": record["payload"],
        "warnings": record["warnings"],
    })


@router.patch("/{validation_id}", response_model=ValidationResult)
def decide_validation(validation_id: str, decision: ValidationDecision):
    """
    Human submits a decision: approve, reject, or edit-and-approve.

    Examples:
      PATCH /validations/{id}
      { "action": "approve" }

      { "action": "reject", "reason": "Tasks are duplicates of existing work." }

      { "action": "edit_and_approve", "edited_tasks": [...] }
    """
    try:
        return process_decision(validation_id, decision)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write to database: {str(e)}")


@router.get("/", response_model=list[ValidationResponse])
def list_pending_validations(project_id: str):
    """List all pending validations for a project."""
    db = get_agent_db()
    try:
        records = (
            db.query(ValidationRequest)
            .filter(
                ValidationRequest.project_id == project_id,
                ValidationRequest.status == ValidationStatus.PENDING,
            )
            .order_by(ValidationRequest.created_at.desc())
            .all()
        )
        return [
            ValidationResponse(
                validation_id=str(r.id),
                agent=r.agent_name,
                action=r.action,
                status=r.status,
                created_at=r.created_at.isoformat(),
                expires_at=r.expires_at.isoformat(),
                payload=json.loads(r.payload),
                warnings=json.loads(r.warnings),
            )
            for r in records
        ]
    finally:
        db.close()


# ─── Helper converters ────────────────────────────────────────────────────────

def _mapper_result_to_payload(result: MapperResult) -> dict:
    payload: dict = {}
    if result.mapped_tasks:
        payload["tasks"] = [
            {
                "title": t.title,
                "description": t.description,
                "priority": t.priority,
                "labels": t.labels,
                "estimated_hours": t.estimated_hours,
                "story_points": t.story_points,
                "acceptance_criteria": t.acceptance_criteria,
                "duplicate_of": t.duplicate_of,
                "split_from": t.split_from,
            }
            for t in result.mapped_tasks
        ]
    if result.mapped_assignments:
        payload["assignments"] = [
            {
                "task_id": a.task_id,
                "task_title": a.task_title,
                "assignee_id": a.assignee_id,
                "assignee_name": a.assignee_name,
                "assignee_reason": a.assignee_reason,
                "reviewer_id": a.reviewer_id,
                "reviewer_name": a.reviewer_name,
                "reviewer_reason": a.reviewer_reason,
            }
            for a in result.mapped_assignments
        ]
    if result.mapped_sprint:
        s = result.mapped_sprint
        payload["sprint"] = {
            "name": s.name,
            "goal": s.goal,
            "start_date": s.start_date,
            "end_date": s.end_date,
            "total_capacity_points": s.total_capacity_points,
            "planned_points": s.planned_points,
            "buffer_points": s.buffer_points,
            "tasks_to_split": s.tasks_to_split,
        }
        payload["selected_task_ids"] = s.selected_task_ids
    return payload


def _dict_to_mapped_task(d: dict, project_id: str) -> MappedTask:
    return MappedTask(
        title=d.get("title", ""),
        description=d.get("description", ""),
        priority=d.get("priority", "P3"),
        labels=d.get("labels", []),
        estimated_hours=d.get("estimated_hours"),
        story_points=d.get("story_points"),
        acceptance_criteria=d.get("acceptance_criteria", []),
        duplicate_of=d.get("duplicate_of"),
        split_from=d.get("split_from"),
        project_id=project_id,
    )


def _dict_to_mapped_assignment(d: dict) -> MappedAssignment:
    return MappedAssignment(
        task_id=d.get("task_id", ""),
        task_title=d.get("task_title", ""),
        assignee_id=d.get("assignee_id", ""),
        assignee_name=d.get("assignee_name", ""),
        assignee_reason=d.get("assignee_reason", ""),
        reviewer_id=d.get("reviewer_id"),
        reviewer_name=d.get("reviewer_name"),
        reviewer_reason=d.get("reviewer_reason"),
    )


def _dict_to_mapped_sprint(d: dict, task_ids: list[str]) -> MappedSprint:
    return MappedSprint(
        name=d.get("name", "Sprint"),
        goal=d.get("goal", ""),
        start_date=d.get("start_date", ""),
        end_date=d.get("end_date", ""),
        total_capacity_points=d.get("total_capacity_points", 0),
        planned_points=d.get("planned_points", 0),
        buffer_points=d.get("buffer_points", 0),
        selected_task_ids=task_ids,
        tasks_to_split=d.get("tasks_to_split", []),
        warnings=d.get("warnings", []),
    )
