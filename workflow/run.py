from task_agent import TaskAgent
from mapper import map_agent_output
from validation import store_validation
from assignment_agent import AssignmentAgent
from planning_agent import PlanningAgent

agent = TaskAgent()
result = agent.run(
    user_input="Create tasks for implementing JWT authentication in our FastAPI backend",
    context={"project_id": "proj_abc123"}
)

mapper_result = map_agent_output("task_agent", result["raw_output"], {"project_id": "proj_abc123"})
validation_id = store_validation(mapper_result, project_id="proj_abc123", requested_by="user_xyz")
print(f"Review at: GET /validations/{validation_id}")


agent = AssignmentAgent()
result = agent.run(
    user_input="Assign the JWT auth tasks to the best available team member",
    context={"project_id": "proj_abc123", "task_ids": ["task_1", "task_2"]}
)
# → same flow: map → validate → approve
agent = PlanningAgent()
result = agent.run(
    user_input="Plan sprint 4 for our project. We have 5 developers for 2 weeks.",
    context={"project_id": "proj_abc123"}
)
