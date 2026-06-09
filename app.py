from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any, List, Optional
import uuid

from graph.graph_builder import build_graph
from main import build_initial_state
from db.persist import ensure_project, ensure_users, map_priority
from agents.planning_agent import _derive_sprint_name, _is_generic_sprint_name

app = FastAPI(
    title="AgileAI Agent Orchestration API",
    description="REST API for the LangGraph project management multi-agent orchestrator.",
    version="1.0.0"
)

# Enable CORS for easy cross-project frontend and backend consumption
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TeamMemberInput(BaseModel):
    id: str
    name: str
    skills: List[str] = Field(default_factory=list)
    current_load: int = 0

class OrchestratePayload(BaseModel):
    user_input: str
    project_id: str = "default"
    team_members: Optional[List[TeamMemberInput]] = None
    skip_db_write: bool = True

@app.get("/")
def read_root():
    return {
        "message": "Welcome to AgileAI Agent API",
        "docs_url": "/docs",
        "status": "healthy"
    }

@app.get("/api/health")
def health_check():
    return {"status": "healthy"}

@app.post("/api/orchestrate")
def orchestrate(payload: OrchestratePayload):
    try:
        # 1. Convert team members to dictionaries if provided
        team_list = None
        if payload.team_members is not None:
            team_list = [t.model_dump() for t in payload.team_members]

        # 2. Database safety setup
        ensure_project(payload.project_id, name=f"Project {payload.project_id}")
        if team_list:
            ensure_users(team_list)

        # 3. Build initial graph state
        state = build_initial_state(
            user_input=payload.user_input,
            project_id=payload.project_id,
            team_members=team_list
        )
        state["skip_db_write"] = payload.skip_db_write

        # 4. Invoke the LangGraph workflow
        graph = build_graph()
        out = graph.invoke(state, {"recursion_limit": 25})

        # 5. Extract and format outputs to match the user's Prisma models
        backlog = out.get("backlog") or []
        sprint_plan_tasks = out.get("sprint_plan") or []
        assignments_tasks = out.get("assignments") or []
        sprint_goal = out.get("sprint_goal")
        planning_extra = out.get("planning_extra") or {}
        assignment_extra = out.get("assignment_extra") or {}
        err = out.get("error")

        if err:
            return {"error": err}

        # Combine all tasks that were created, planned, or assigned
        all_tasks_by_id = {}
        for t in backlog:
            all_tasks_by_id[t["id"]] = t
        for t in sprint_plan_tasks:
            all_tasks_by_id[t["id"]] = t
        for t in assignments_tasks:
            all_tasks_by_id[t["id"]] = t

        # Format sprint_plan
        sprint_block = planning_extra.get("sprint") or {}
        sprint_plan_resp = None
        if sprint_plan_tasks or sprint_goal:
            goal_text = sprint_goal or sprint_block.get("goal") or ""
            sprint_name = sprint_block.get("name")
            if _is_generic_sprint_name(sprint_name):
                sprint_name = _derive_sprint_name(goal_text, sprint_plan_tasks)
            planned_from_tasks = sum(
                int(t.get("story_points") or 0) for t in sprint_plan_tasks
            )
            planned_points = (
                planned_from_tasks
                if planned_from_tasks > 0
                else int(sprint_block.get("planned_points") or 0)
            )
            sprint_plan_resp = {
                "name": sprint_name or "Upcoming Sprint",
                "goal": goal_text,
                "totalCapacityPoints": int(sprint_block.get("total_capacity_points") or 0),
                "plannedPoints": planned_points,
                "bufferPoints": int(sprint_block.get("buffer_points") or 0),
                "color": sprint_block.get("color") or "#0052CC",
                "status": "DRAFT"
            }

        # Format assignments to align with agents.Assignment in Prisma
        formatted_assignments = []
        assignment_list = assignment_extra.get("assignments") or []
        for ass in assignment_list:
            formatted_assignments.append({
                "taskId": ass.get("task_id"),
                "projectId": payload.project_id,
                "assigneeId": ass.get("assigned_to", {}).get("user_id"),
                "reviewerId": ass.get("reviewer", {}).get("user_id"),
                "assigneeReason": ass.get("assigned_to", {}).get("reason"),
                "reviewerReason": ass.get("reviewer", {}).get("reason"),
                "applied": True
            })

        assignment_by_task = {
            a["taskId"]: a for a in formatted_assignments if a.get("taskId")
        }

        # Format tasks to align with agents.Task in Prisma
        formatted_tasks = []
        for tid, t in all_tasks_by_id.items():
            assignment = assignment_by_task.get(tid) or {}
            formatted_tasks.append({
                "id": t.get("id"),
                "projectId": payload.project_id,
                "sprintPlanId": t.get("sprint_plan_id"),
                "assigneeId": t.get("assignee_id") or assignment.get("assigneeId"),
                "reviewerId": t.get("reviewer_id") or assignment.get("reviewerId"),
                "reporterId": "system",
                "creatorId": "system",
                "title": t.get("title", ""),
                "description": t.get("description"),
                "acceptanceCriteria": t.get("acceptance_criteria") or [],
                "status": "TODO" if t.get("sprint_plan_id") else "BACKLOG",
                "type": "TASK",
                "priority": map_priority(t.get("priority")),
                "labels": t.get("labels") or [],
                "storyPoints": t.get("story_points"),
                "estimatedHours": float(t.get("estimated_hours")) if t.get("estimated_hours") is not None else None,
                "sprintPosition": 0.0,
                "boardPosition": -1.0,
                "sprintColor": None,
                "deletedAt": None,
                "isBlocked": False,
                "blockedReason": None,
                "aiGenerated": True,
                "key": t.get("key") or f"{payload.project_id.upper()[:10]}-{tid[:4]}"
            })

        # Format next_actions
        formatted_next_actions = []
        next_action_list = assignment_extra.get("next_actions") or []
        for na in next_action_list:
            formatted_next_actions.append({
                "userId": na.get("user_id"),
                "recommended_taskId": na.get("recommended_task_id"),
                "reason": na.get("reason")
            })

        warnings = []
        warnings.extend(planning_extra.get("warnings") or [])
        warnings.extend(assignment_extra.get("warnings") or [])

        return {
            "sprint_goal": sprint_goal,
            "sprint_plan": sprint_plan_resp,
            "tasks": formatted_tasks,
            "assignments": formatted_assignments,
            "next_actions": formatted_next_actions,
            "warnings": warnings,
            "error": None
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
