"""Single entry for chat completions: Groq and Ollama support."""

from __future__ import annotations

import time
from typing import Any

from config import (
    GROQ_API_KEY,
    GROQ_BASE_URL,
    GROQ_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    get_llm_provider,
    is_llm_dry_run,
    LLM_INITIAL_BACKOFF,
    LLM_MAX_BACKOFF,
    LLM_MAX_RETRIES,
)


class LLMQuotaError(RuntimeError):
    """429 / rate limit or quota exceeded from the active provider."""


def call_llm(prompt: str) -> str:
    """One-shot text generation used by supervisor and BaseAgent."""
    if is_llm_dry_run():
        raise RuntimeError("call_llm must not run in dry_run mode.")

    provider = get_llm_provider()
    
    if provider == "ollama":
        return _call_ollama_with_retry(prompt)
    elif provider == "groq":
        if not GROQ_API_KEY:
            raise RuntimeError(
                "No Groq API key. Set GROQ_API_KEY in .env, or use LLM_PROVIDER=ollama."
            )
        return _call_groq_with_retry(prompt)
    else:
        raise RuntimeError(f"Unknown LLM provider: {provider}")


def _call_groq_with_retry(prompt: str) -> str:
    """Call Groq API with exponential backoff retry logic for rate limits."""
    from openai import APIError, OpenAI, RateLimitError

    client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)
    
    for attempt in range(LLM_MAX_RETRIES + 1):
        try:
            resp = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            text = resp.choices[0].message.content
            return (text or "").strip()
            
        except RateLimitError as e:
            if attempt == LLM_MAX_RETRIES:
                raise LLMQuotaError(
                    f"Groq rate limit (429) after {LLM_MAX_RETRIES} retries. "
                    "Wait and retry or check https://console.groq.com/docs/rate-limits"
                ) from e
            
            # Calculate exponential backoff
            backoff = min(LLM_INITIAL_BACKOFF * (2 ** attempt), LLM_MAX_BACKOFF)
            print(f"[LLM] Rate limit hit (attempt {attempt + 1}/{LLM_MAX_RETRIES + 1}), "
                  f"retrying in {backoff:.1f}s...")
            time.sleep(backoff)
            
        except APIError as e:
            status_code = getattr(e, "status_code", None)
            if status_code == 429:
                if attempt == LLM_MAX_RETRIES:
                    raise LLMQuotaError(
                        f"Groq API error 429 after {LLM_MAX_RETRIES} retries: {str(e)}"
                    ) from e
                
                backoff = min(LLM_INITIAL_BACKOFF * (2 ** attempt), LLM_MAX_BACKOFF)
                print(f"[LLM] API error 429 (attempt {attempt + 1}/{LLM_MAX_RETRIES + 1}), "
                      f"retrying in {backoff:.1f}s...")
                time.sleep(backoff)
            else:
                # For non-429 errors, don't retry
                raise
                
        except Exception as e:
            # For unexpected errors, don't retry
            raise
    
    # This should never be reached, but just in case
    raise LLMQuotaError("Failed to complete LLM call after all retries")


def _call_groq(prompt: str) -> str:
    """Legacy function - kept for compatibility. Use _call_groq_with_retry instead."""
    return _call_groq_with_retry(prompt)


def _call_ollama_with_retry(prompt: str) -> str:
    """Call Ollama API with exponential backoff retry logic."""
    import requests
    
    url = f"{OLLAMA_BASE_URL}/api/generate"
    
    for attempt in range(LLM_MAX_RETRIES + 1):
        try:
            response = requests.post(
                url,
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.2,
                    }
                },
                timeout=120  # Ollama can be slower than cloud APIs
            )
            response.raise_for_status()
            data = response.json()
            text = data.get("response", "")
            return text.strip()
            
        except requests.exceptions.Timeout as e:
            if attempt == LLM_MAX_RETRIES:
                raise LLMQuotaError(
                    f"Ollama request timeout after {LLM_MAX_RETRIES} retries."
                ) from e
            
            backoff = min(LLM_INITIAL_BACKOFF * (2 ** attempt), LLM_MAX_BACKOFF)
            print(f"[LLM] Ollama timeout (attempt {attempt + 1}/{LLM_MAX_RETRIES + 1}), "
                  f"retrying in {backoff:.1f}s...")
            time.sleep(backoff)
            
        except requests.exceptions.ConnectionError as e:
            if attempt == LLM_MAX_RETRIES:
                raise LLMQuotaError(
                    f"Ollama connection error after {LLM_MAX_RETRIES} retries: {str(e)}. "
                    "Make sure Ollama is running with 'ollama serve'"
                ) from e
            
            backoff = min(LLM_INITIAL_BACKOFF * (2 ** attempt), LLM_MAX_BACKOFF)
            print(f"[LLM] Ollama connection error (attempt {attempt + 1}/{LLM_MAX_RETRIES + 1}), "
                  f"retrying in {backoff:.1f}s...")
            time.sleep(backoff)
            
        except Exception as e:
            # For other errors, don't retry
            raise LLMQuotaError(f"Ollama API error: {str(e)}") from e
    
    # This should never be reached, but just in case
    raise LLMQuotaError("Failed to complete Ollama call after all retries")
