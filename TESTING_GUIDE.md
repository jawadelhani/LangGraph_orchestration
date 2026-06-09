# Complete End-to-End Testing Guide

This guide walks you through testing the AgileAI Agents project from database setup to verification.

## Prerequisites

- PostgreSQL 15+ installed and running
- Python 3.14+
- Your PostgreSQL database named `agileai` with two schemas: `business` and `agents`

## Step 1: Database Setup

### 1.1 Create Database and Schemas

Connect to PostgreSQL and run:

```sql
-- Create database
CREATE DATABASE agileai;

-- Connect to the database
\c agileai

-- Create schemas
CREATE SCHEMA business;
CREATE SCHEMA agents;
```

### 1.2 Verify Schemas

```sql
SELECT schema_name 
FROM information_schema.schemata 
WHERE schema_name IN ('business', 'agents');
```

Expected output:
```
 schema_name 
-------------
 business
 agents
```

## Step 2: Configure Environment

### 2.1 Create `.env` File

Create `Agents/.env` with:

```env
# Database
DATABASE_URL=postgresql+psycopg2://postgres:your_password@localhost:5432/agileai

# LLM Configuration
LLM_MODE=dry_run

# Optional: For live API calls
# GROQ_API_KEY=your_groq_api_key
# GROQ_MODEL=llama-3.3-70b-versatile
```

**Note**: Replace `your_password` with your PostgreSQL password.

### 2.2 Install Dependencies

```bash
cd Agents
pip install -r requirements.txt
```

## Step 3: Initialize Database Tables

### 3.1 Run Database Initialization

```bash
cd Agents
python -c "from db.session import init_db; init_db(); print('Database initialized successfully')"
```

This will create all tables in both schemas:
- `business` schema: Project, User, MemberSkill
- `agents` schema: SprintPlan, Task, Assignment, etc.

### 3.2 Verify Tables Created

```sql
-- Check business schema tables
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'business';

-- Check agents schema tables
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'agents';
```

Expected tables in `business`:
- Project
- User
- MemberSkill

Expected tables in `agents`:
- SprintPlan
- Task
- Assignment
- AgentSession
- ValidationRequest
- AgentContext
- EventLog
- Notification
- VelocityRecord
- RiskAssessment
- WorkflowTransition
- BlockedTask
- BottleneckRecord
- WorkflowSuggestion
- WebhookEvent
- AutomationRule
- AutomationExecution
- AutomationSuggestion
- PullRequestLink
- DuplicateDetection
- IssueSplitSuggestion
- Comment

## Step 4: Seed Test Data

### 4.1 Create Test Users and Project

Run this Python script to seed test data:

```python
# seed_test_data.py
from db.persist import ensure_project, ensure_users
from db.session import init_db

init_db()

# Create project
ensure_project(
    project_id="test-project-001",
    name="Test Project"
)

# Create users (matching your database)
users = [
    {
        "id": "user_2PvBRngdvenUlFvQNAWbXIvYVy5",
        "name": "Sheldon Cooper",
        "email": "sheldon.cooper@jira.com",
        "avatar": "https://images.clerk.dev/uploaded/img_2Pwinee7Eg6qoSgqailCZSJt3uS.webp",
        "skills": ["backend", "Python", "PostgreSQL"],
        "current_load": 0
    },
    {
        "id": "user_2PwZmH2xP5aE0svR6hDH4AwDlcu",
        "name": "Joe Rogan",
        "email": "joe.rogan@jira.com",
        "avatar": "https://images.clerk.dev/uploaded/img_2PwZslOi493tjduHiBADgDxhHlg.png",
        "skills": ["frontend", "React", "UI"],
        "current_load": 0
    },
    {
        "id": "user_2PwYvTgm6kvgJIbWwN0xsei8izu",
        "name": "Steve Jobs",
        "email": "steve.jobs@jira.com",
        "avatar": "https://images.clerk.dev/uploaded/img_2PwjGSsR9nGqEhAyt5nydgXhBI1.webp",
        "skills": ["product", "design", "strategy"],
        "current_load": 0
    }
]

ensure_users(users)
print("Test data seeded successfully!")
```

Run it:
```bash
python seed_test_data.py
```

### 4.2 Verify Data in Database

```sql
-- Check users
SELECT id, name, email FROM business."User";

-- Check project
SELECT id, name, key FROM business."Project";

-- Check skills
SELECT userId, skill, level FROM business."MemberSkill";
```

## Step 5: Test the LangGraph Workflow

### 5.1 Run the Test Script

```bash
cd Agents
python test_recursion.py
```

Expected output:
```
Building initial state...
Ensuring project and users exist in DB...
Building graph...
Invoking graph with recursion_limit=50...
[SUPERVISOR] State: backlog=0, sprint=0, assigned=0/0
[SUPERVISOR] Routing to task agent
[SUPERVISOR] State: backlog=1, sprint=0, assigned=0/0
[SUPERVISOR] Routing to planning agent
[SUPERVISOR] State: backlog=1, sprint=1, assigned=0/1
[SUPERVISOR] Routing to assignment agent (0/1 assigned)
[SUPERVISOR] State: backlog=1, sprint=1, assigned=1/1
[SUPERVISOR] All conditions met, routing to END

=== SUCCESS ===
Backlog items: 1
Sprint plan items: 1
Assignments: 1
Error: None
```

### 5.2 Verify Database After Test

```sql
-- Check tasks created
SELECT id, title, status, priority, assigneeId 
FROM agents."Task" 
WHERE projectId = 'test-project-001';

-- Check sprint plan
SELECT id, name, goal, status, totalCapacityPoints, plannedPoints 
FROM agents."SprintPlan" 
WHERE projectId = 'test-project-001';

-- Check assignments
SELECT id, taskId, assigneeId, reviewerId, applied 
FROM agents."Assignment" 
WHERE projectId = 'test-project-001';
```

## Step 6: Test the FastAPI Endpoint

### 6.1 Start the Server

```bash
cd Agents
uvicorn app:app --reload --port 8000
```

### 6.2 Test the Health Endpoint

```bash
curl http://localhost:8000/api/health
```

Expected response:
```json
{"status": "healthy"}
```

### 6.3 Test the Orchestrate Endpoint

```bash
curl -X POST http://localhost:8000/api/orchestrate \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "We need a login page with Google OAuth. Plan the sprint and assign tasks.",
    "project_id": "test-project-001",
    "team_members": [
      {
        "id": "user_2PvBRngdvenUlFvQNAWbXIvYVy5",
        "name": "Sheldon Cooper",
        "skills": ["backend", "Python", "PostgreSQL"],
        "current_load": 0
      },
      {
        "id": "user_2PwZmH2xP5aE0svR6hDH4AwDlcu",
        "name": "Joe Rogan",
        "skills": ["frontend", "React", "UI"],
        "current_load": 0
      },
      {
        "id": "user_2PwYvTgm6kvgJIbWwN0xsei8izu",
        "name": "Steve Jobs",
        "skills": ["product", "design", "strategy"],
        "current_load": 0
      }
    ],
    "skip_db_write": true
  }'
```

Expected response structure:
```json
{
  "sprint_goal": "Deliver the backlog slice with a working increment.",
  "sprint_plan": {
    "name": "Sprint 1 (dry-run)",
    "goal": "Deliver the backlog slice with a working increment.",
    "totalCapacityPoints": 40,
    "plannedPoints": 2,
    "bufferPoints": 6,
    "color": "#0052CC",
    "status": "DRAFT"
  },
  "tasks": [
    {
      "id": "...",
      "projectId": "test-project-001",
      "title": "Implement requested feature",
      "description": "...",
      "status": "TODO",
      "priority": "P2_HIGH",
      "assigneeId": "user_2PvBRngdvenUlFvQNAWbXIvYVy5",
      "reviewerId": "user_2PwZmH2xP5aE0svR6hDH4AwDlcu",
      "aiGenerated": true
    }
  ],
  "assignments": [
    {
      "taskId": "...",
      "assigneeId": "user_2PvBRngdvenUlFvQNAWbXIvYVy5",
      "reviewerId": "user_2PwZmH2xP5aE0svR6hDH4AwDlcu",
      "assigneeReason": "dry_run: round-robin by order",
      "reviewerReason": "dry_run: next teammate reviews"
    }
  ],
  "next_actions": [
    {
      "userId": "user_2PvBRngdvenUlFvQNAWbXIvYVy5",
      "recommended_taskId": "...",
      "reason": "dry_run: your assigned sprint task"
    }
  ],
  "warnings": ["dry_run: no API call"],
  "error": null
}
```

### 6.4 Test with Database Write Enabled

To test actual database writes:

```bash
curl -X POST http://localhost:8000/api/orchestrate \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "Add user registration feature",
    "project_id": "test-project-001",
    "team_members": [
      {
        "id": "user_2PvBRngdvenUlFvQNAWbXIvYVy5",
        "name": "Sheldon Cooper",
        "skills": ["backend", "Python", "PostgreSQL"],
        "current_load": 0
      },
      {
        "id": "user_2PwZmH2xP5aE0svR6hDH4AwDlcu",
        "name": "Joe Rogan",
        "skills": ["frontend", "React", "UI"],
        "current_load": 0
      }
    ],
    "skip_db_write": false
  }'
```

Then verify in database:
```sql
SELECT id, title, status FROM agents."Task" WHERE projectId = 'test-project-001';
```

## Step 7: Run Unit Tests

### 7.1 Run All Tests

```bash
cd Agents
pytest tests/ -v
```

### 7.2 Run Specific Test Files

```bash
# Test JSON parsing
pytest tests/test_json.py -v

# Test router logic
pytest tests/test_router.py -v

# Test API endpoint
pytest tests/test_api.py -v
```

## Step 8: Cleanup (Optional)

To clean up test data:

```sql
-- Delete test data
DELETE FROM agents."Assignment" WHERE projectId = 'test-project-001';
DELETE FROM agents."Task" WHERE projectId = 'test-project-001';
DELETE FROM agents."SprintPlan" WHERE projectId = 'test-project-001';
DELETE FROM business."MemberSkill" WHERE userId IN (
  'user_2PvBRngdvenUlFvQNAWbXIvYVy5',
  'user_2PwZmH2xP5aE0svR6hDH4AwDlcu',
  'user_2PwYvTgm6kvgJIbWwN0xsei8izu'
);
DELETE FROM business."User" WHERE id IN (
  'user_2PvBRngdvenUlFvQNAWbXIvYVy5',
  'user_2PwZmH2xP5aE0svR6hDH4AwDlcu',
  'user_2PwYvTgm6kvgJIbWwN0xsei8izu'
);
DELETE FROM business."Project" WHERE id = 'test-project-001';
```

## Troubleshooting

### Issue: "Recursion limit of 25 reached"
**Solution**: Set `LLM_MODE=dry_run` in `.env` or get a valid Groq API key.

### Issue: "relation does not exist"
**Solution**: Run `init_db()` to create tables, or verify schemas exist in PostgreSQL.

### Issue: "Groq rate limit (429)"
**Solution**: Use dry-run mode for testing, or wait and retry with a valid API key.

### Issue: "Planning needs a non-empty backlog"
**Solution**: Ensure the task agent runs successfully before planning agent. Check supervisor routing logs.

## Summary

The complete testing flow:
1. **Database Setup** → Create database and schemas
2. **Configuration** → Set up `.env` with database URL and LLM mode
3. **Table Creation** → Run `init_db()` to create all tables
4. **Seed Data** → Create test users and project
5. **Workflow Test** → Run `test_recursion.py` to verify LangGraph
6. **API Test** → Start FastAPI server and test endpoints
7. **Database Verification** → Query database to verify data persistence
8. **Unit Tests** → Run pytest to verify individual components
