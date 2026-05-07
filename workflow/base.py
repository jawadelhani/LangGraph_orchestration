"""
Base agent class — all agents inherit from this.
Handles Gemini API calls, tool execution loop, and session logging.
"""

import json
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any

import google.generativeai as genai
from config import GEMINI_API_KEY, GEMINI_MODEL
from db import get_agent_db
from models import AgentSession

genai.configure(api_key=GEMINI_API_KEY)


class BaseAgent(ABC):
    name: str = "base_agent"
    description: str = ""

    def __init__(self):
        self.model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=self.system_prompt(),
            tools=self._build_tools(),
        )

    @abstractmethod
    def system_prompt(self) -> str:
        pass

    @abstractmethod
    def tool_definitions(self) -> list[dict]:
        pass

    @abstractmethod
    def execute_tool(self, name: str, args: dict) -> Any:
        pass

    def _build_tools(self):
        """Build tools from definitions for google.generativeai."""
        from google.generativeai.types import Tool, FunctionDeclaration, Schema
        
        decls = self.tool_definitions()
        if not decls:
            return []
        
        # Convert dict-based definitions to FunctionDeclaration objects
        function_decls = []
        for d in decls:
            params = d.get('parameters', {})
            func_decl = FunctionDeclaration(
                name=d['name'],
                description=d.get('description', ''),
                parameters=Schema(
                    type='object',
                    properties=params.get('properties', {}),
                    required=params.get('required', [])
                )
            )
            function_decls.append(func_decl)
        
        return [Tool(function_declarations=function_decls)]

    def run(self, user_input: str, context: dict = {}) -> dict:
        """
        Main agentic loop:
        1. Send message to Gemini
        2. If Gemini calls a tool → execute it → send result back
        3. Repeat until Gemini returns a final text response
        4. Return structured result
        """
        session_id = str(uuid.uuid4())
        start = time.time()
        tools_called = []

        enriched_input = f"{user_input}\n\nContext: {json.dumps(context)}" if context else user_input

        chat = self.model.start_chat(enable_automatic_function_calling=False)
        
        final_text = ""
        max_iterations = 10
        first_message = True

        for iteration in range(max_iterations):
            # Send message to Gemini
            if first_message:
                response = chat.send_message(enriched_input)
                first_message = False
            else:
                response = chat.send_message(enriched_input)
            
            candidate = response.candidates[0]

            # Check if Gemini wants to call a tool
            tool_calls = [
                part for part in candidate.content.parts
                if hasattr(part, "function_call") and part.function_call.name
            ]

            if not tool_calls:
                # Final text response
                final_text = "".join(
                    part.text for part in candidate.content.parts
                    if hasattr(part, "text") and part.text
                )
                break

            # Execute each tool call and build response
            tool_results = []
            for part in tool_calls:
                fc = part.function_call
                tool_name = fc.name
                tool_args = dict(fc.args)
                tools_called.append({"tool": tool_name, "args": tool_args})

                try:
                    result = self.execute_tool(tool_name, tool_args)
                except Exception as e:
                    result = {"error": str(e)}

                tool_results.append(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=tool_name,
                            response={"result": json.dumps(result) if not isinstance(result, str) else result},
                        )
                    )
                )

            # Send tool results back as next message
            chat.send_message([genai.protos.Content(parts=tool_results, role="tool")])

        duration_ms = int((time.time() - start) * 1000)

        # Log session to DB
        self._log_session(
            session_id=session_id,
            input_text=user_input,
            output_text=final_text,
            tools_called=tools_called,
            duration_ms=duration_ms,
            context=context,
        )

        return {
            "session_id": session_id,
            "agent": self.name,
            "raw_output": final_text,
            "tools_called": tools_called,
            "duration_ms": duration_ms,
        }

    def _log_session(self, session_id, input_text, output_text, tools_called, duration_ms, context):
        db = get_agent_db()
        try:
            session = AgentSession(
                id=session_id,
                agent_name=self.name,
                input=input_text,
                output=output_text,
                tools_called=json.dumps(tools_called),
                duration_ms=duration_ms,
                context=json.dumps(context),
            )
            db.add(session)
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"[BaseAgent] Failed to log session: {e}")
        finally:
            db.close()
