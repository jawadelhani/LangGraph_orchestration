"""Shared agent contract (matches the AgileAI-style class pattern)."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from config import is_llm_dry_run
from llm.gemini_client import LLMQuotaError, call_gemini


class BaseAgent(ABC):
    name: str = "base_agent"
    description: str = ""

    @abstractmethod
    def system_prompt(self) -> str:
        """Instructions for the model (role, rules, output JSON shape)."""
        raise NotImplementedError

    def tool_definitions(self) -> list[dict[str, Any]]:
        return []

    def execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        return {"error": f"Unknown tool: {name}"}

    def run(self, user_input: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        if is_llm_dry_run():
            raise RuntimeError("BaseAgent.run is not used in dry_run; nodes use local stubs.")
        ctx = dict(context or {})
        tools = json.dumps(self.tool_definitions(), indent=2, ensure_ascii=False)
        prompt = (
            f"{self.system_prompt().strip()}\n\n"
            f"Available tools (schemas; data may already appear in Context):\n{tools}\n\n"
            f"Context JSON:\n{json.dumps(ctx, ensure_ascii=False, default=str)}\n\n"
            f"User message:\n{user_input}\n"
        )
        try:
            raw = call_gemini(prompt)
        except LLMQuotaError as e:
            return {"raw_output": "", "llm_error": str(e)}
        return {"raw_output": raw}
