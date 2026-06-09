# AgileAI Agents API - Setup and Testing Guide

## Issue Identified: Groq API Rate Limits

The "Recursion limit of 25 reached" error you encountered is caused by **Groq API rate limits (429)**, not a logic problem in the LangGraph workflow.

## Solution Options

### Option 1: Test with Dry-Run Mode (Recommended for Testing)

Set the environment variable to use dry-run mode (no API calls):

```bash
# Windows PowerShell
$env:LLM_MODE = "dry_run"

# Or add to your .env file:
LLM_MODE=dry_run
```

Then run the API:

```bash
cd Agents
uvicorn app:app --reload --port 8000
```

### Option 2: Use a Valid Groq API Key

If you want to use live LLM calls, get a Groq API key from https://console.groq.com/ and add it to your `.env` file:

```env
GROQ_API_KEY=your_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
LLM_MODE=live
```

## Testing the API

### Test Script (Dry-Run Mode)

Run the test script I created:

```bash
cd Agents
python test_recursion.py
```

This will test the full workflow without API calls using your actual database users.

### Manual API Test

Start the server:

```bash
cd Agents
uvicorn app:app --reload --port 8000
```

Then send a POST request with your actual team members from the database:

```bash
curl -X POST http://localhost:8000/api/orchestrate \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "We need a login page with Google OAuth. Plan the sprint and assign tasks.",
    "project_id": "init-project-id-dq8yh-d0as89hjd",
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

## Important Notes

1. **Team Members**: You must pass `team_members` in the API request. If you don't, it will use default test users (Fatima and Youssef) which won't match your database.

2. **Project ID**: Use your actual project ID from the database: `init-project-id-dq8yh-d0as89hjd`

3. **skip_db_write**: Set to `true` for testing to avoid writing to your production database.

4. **Dry-Run Mode**: In dry-run mode, the agents return mock data instead of calling the LLM. This is perfect for testing the workflow without API costs or rate limits.

## Workflow Verification

The correct workflow is:
1. **Task Agent** → Creates backlog tasks from user input
2. **Planning Agent** → Selects tasks for sprint, estimates points, generates sprint goal
3. **Assignment Agent** → Assigns tasks to team members based on skills and workload
4. **Supervisor** → Routes between agents and ends when all work is complete

The test confirmed this workflow works correctly when not hitting API rate limits.
