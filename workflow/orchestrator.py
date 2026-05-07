"""
Orchestrator
============
Entry point for all AI requests. Routes to the right agent,
maps output, stores validation request, returns validation_id to the frontend.

Usage (FastAPI route):
    POST /ai/chat
    { "message": "Create tasks for the auth module", "project_id": "abc123" }

    Response:
    { "validation_id": "...", "agent": "task_agent", "preview": {...} }

Then human approves via:
    PATCH /validations/{validation_id}
    { "action": "approve" }
"""

import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from task_agent import TaskAgent
from assignment_agent import AssignmentAgent
from planning_agent import PlanningAgent
from mapper import map_agent_output
from validation import store_validation


# ─── Request / Response schemas ───────────────────────────────────────────────

class AIRequest(BaseModel):
    message: str
    project_id: str
    sprint_id: str | None = None
    task_ids: list[str] | None = None       # for assignment requests
    requested_by: str = "unknown_user"      # user_id of the requester


class AIResponse(BaseModel):
    validation_id: str
    agent: str
    action: str
    preview: dict                           # mapped payload for quick UI preview
    warnings: list[str]
    message: str


# ─── Intent classifier ────────────────────────────────────────────────────────

TASK_SIGNALS = [
    r"\bcreate\b", r"\badd\b", r"\bgenerate\b", r"\bnew task\b",
    r"\bticket\b", r"\bfeature\b", r"\bbug\b", r"\bstory\b",
    r"\bimprove description\b", r"\bsplit\b",
]

ASSIGNMENT_SIGNALS = [
    r"\bassign\b", r"\bwho should\b", r"\bworkload\b",
    r"\breviewer\b", r"\bavailability\b", r"\bnext task\b",
]

PLANNING_SIGNALS = [
    r"\bsprint\b", r"\bplan\b", r"\bestimate\b", r"\bstory points?\b",
    r"\bvelocity\b", r"\bbacklog\b", r"\bsprint goal\b", r"\bcapacity\b",
]


def classify_intent(message: str) -> str:
    msg = message.lower()
    scores = {
        "task_agent": sum(1 for p in TASK_SIGNALS if re.search(p, msg)),
        "assignment_agent": sum(1 for p in ASSIGNMENT_SIGNALS if re.search(p, msg)),
        "planning_agent": sum(1 for p in PLANNING_SIGNALS if re.search(p, msg)),
    }
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "task_agent"  # default fallback
    return best


# ─── Agent registry ───────────────────────────────────────────────────────────

AGENTS = {
    "task_agent": TaskAgent,
    "assignment_agent": AssignmentAgent,
    "planning_agent": PlanningAgent,
}


# ─── FastAPI Router ───────────────────────────────────────────────────────────

router = APIRouter(prefix="/ai", tags=["AI Orchestrator"])


@router.post("/chat", response_model=AIResponse)
def ai_chat(request: AIRequest):
    """
    Main AI entry point.
    1. Classifies intent
    2. Runs appropriate agent
    3. Maps output to structured objects
    4. Stores pending validation
    5. Returns validation_id + preview to frontend
    """
    agent_name = classify_intent(request.message)
    AgentClass = AGENTS.get(agent_name)

    if not AgentClass:
        raise HTTPException(status_code=400, detail=f"No agent found for intent: {agent_name}")

    # Build context for the agent
    context = {
        "project_id": request.project_id,
        "sprint_id": request.sprint_id,
        "task_ids": request.task_ids,
        "requested_by": request.requested_by,
    }

    # Run the agent
    try:
        agent = AgentClass()
        result = agent.run(user_input=request.message, context=context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")

    # Map raw output to structured objects
    try:
        mapper_result = map_agent_output(
            agent_name=agent_name,
            raw_output=result["raw_output"],
            context=context,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse agent output: {str(e)}")

    # Store pending validation
    validation_id = store_validation(
        mapper_result=mapper_result,
        project_id=request.project_id,
        requested_by=request.requested_by,
    )

    # Build preview for the frontend (what the human will review)
    from validation import _mapper_result_to_payload
    preview = _mapper_result_to_payload(mapper_result)

    return AIResponse(
        validation_id=validation_id,
        agent=agent_name,
        action=mapper_result.action,
        preview=preview,
        warnings=mapper_result.warnings,
        message=f"Agent '{agent_name}' completed. Please review and approve the changes.",
    )
