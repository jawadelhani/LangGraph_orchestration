# Groq Rate Limit (429) Fix

## Problem
The Groq API was returning rate limit errors (429), causing the LangGraph workflow to fail with "Recursion limit of 25 reached" errors.

## Solution
Implemented automatic retry logic with exponential backoff to handle rate limits gracefully.

## Changes Made

### 1. Enhanced LLM Client (`llm/llm_client.py`)
- Added `_call_groq_with_retry()` function with exponential backoff
- Automatically retries on rate limit errors (429)
- Logs retry attempts with backoff times
- Only retries on 429 errors, not other API errors
- Raises `LLMQuotaError` only after all retries are exhausted

### 2. Configuration Options (`config.py`)
Added three new environment variables for retry behavior:

```env
# Maximum number of retry attempts for rate limits (default: 5)
LLM_MAX_RETRIES=5

# Initial backoff time in seconds (default: 1.0)
LLM_INITIAL_BACKOFF=1.0

# Maximum backoff time in seconds (default: 60.0)
LLM_MAX_BACKOFF=60.0
```

## How It Works

### Retry Logic
1. **First attempt**: Try the API call immediately
2. **On 429 error**: Wait using exponential backoff
   - Attempt 1: Wait 1 second
   - Attempt 2: Wait 2 seconds
   - Attempt 3: Wait 4 seconds
   - Attempt 4: Wait 8 seconds
   - Attempt 5: Wait 16 seconds
   - (Capped at LLM_MAX_BACKOFF)
3. **After max retries**: Raise `LLMQuotaError` with helpful message

### Example Output
```
[LLM] Rate limit hit (attempt 1/6), retrying in 1.0s...
[LLM] Rate limit hit (attempt 2/6), retrying in 2.0s...
[LLM] Rate limit hit (attempt 3/6), retrying in 4.0s...
```

## Configuration Examples

### Conservative (More Retries, Longer Waits)
```env
LLM_MAX_RETRIES=10
LLM_INITIAL_BACKOFF=2.0
LLM_MAX_BACKOFF=120.0
```

### Aggressive (Fewer Retries, Shorter Waits)
```env
LLM_MAX_RETRIES=3
LLM_INITIAL_BACKOFF=0.5
LLM_MAX_BACKOFF=30.0
```

### Disable Retries (Fail Fast)
```env
LLM_MAX_RETRIES=0
```

## Usage

### With Dry-Run Mode (Recommended for Testing)
```env
LLM_MODE=dry_run
```
No API calls, no rate limits.

### With Live API and Retry Logic
```env
LLM_MODE=live
GROQ_API_KEY=your_api_key_here
LLM_MAX_RETRIES=5
LLM_INITIAL_BACKOFF=1.0
LLM_MAX_BACKOFF=60.0
```

## Testing

Test the retry logic by running the workflow:

```bash
cd Agents
python test_recursion.py
```

Or start the API server:

```bash
uvicorn app:app --reload --port 8000
```

## Benefits

1. **Automatic Recovery**: No manual intervention needed for temporary rate limits
2. **Configurable**: Adjust retry behavior based on your needs
3. **Exponential Backoff**: Respects Groq's rate limit recovery patterns
4. **Logging**: Clear visibility into retry attempts
5. **Graceful Degradation**: Only fails after exhausting all retries

## Groq Rate Limits

As of Groq's documentation:
- Free tier: 30 requests/minute
- Paid tier: Higher limits depending on plan

Check your current limits at: https://console.groq.com/docs/rate-limits

## Troubleshooting

### Still Getting Rate Limit Errors
1. Increase `LLM_MAX_RETRIES` (e.g., to 10)
2. Increase `LLM_INITIAL_BACKOFF` (e.g., to 2.0)
3. Consider upgrading your Groq plan for higher limits
4. Use dry-run mode for testing

### Workflow Still Failing
If you're still seeing "Recursion limit of 25 reached" after this fix:
1. Check that `LLM_MODE` is set correctly
2. Verify your `GROQ_API_KEY` is valid
3. Check the logs for retry attempts
4. Ensure the retry configuration is loaded correctly

## Monitoring

The retry logic prints log messages like:
```
[LLM] Rate limit hit (attempt 1/6), retrying in 1.0s...
```

Monitor these logs to:
- See how often rate limits occur
- Adjust retry configuration if needed
- Identify if you need a higher Groq tier
