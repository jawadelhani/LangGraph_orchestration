"""Deprecated shim — use `llm.llm_client.call_llm`."""

from llm.llm_client import LLMQuotaError, call_gemini, call_llm

__all__ = ["LLMQuotaError", "call_gemini", "call_llm"]
