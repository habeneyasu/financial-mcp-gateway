"""Gemini client and MCP ↔ LLM tool wire format."""

from __future__ import annotations

import asyncio
import copy
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, cast

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from mcp_types import CallToolResult, TextContent, Tool as MCPTool

from config import config
from financial_mcp_gateway.agent.schema import AgentConfigurationError, AgentError


@dataclass
class FunctionCallPart:
    name: str
    arguments: str


@dataclass
class ToolCallPart:
    id: str
    function: FunctionCallPart
    type: str = "function"


@dataclass
class AssistantMessage:
    role: str = "assistant"
    content: str | None = None
    tool_calls: list[ToolCallPart] | None = None

    def model_dump(self, *, exclude_none: bool = False) -> dict[str, Any]:
        out: dict[str, Any] = {"role": self.role}
        if self.content is not None:
            out["content"] = self.content
        if self.tool_calls:
            out["tool_calls"] = [
                {
                    "id": call.id,
                    "type": call.type,
                    "function": {"name": call.function.name, "arguments": call.function.arguments},
                }
                for call in self.tool_calls
            ]
        return out


@dataclass
class CompletionChoice:
    message: AssistantMessage


@dataclass
class Completion:
    choices: list[CompletionChoice] = field(default_factory=list)


class GeminiClient:
    """Async wrapper around the Gemini generate_content API."""

    def __init__(self) -> None:
        if not config.GEMINI_API_KEY:
            raise AgentConfigurationError("GEMINI_API_KEY is not set")
        self._client = genai.Client(api_key=config.GEMINI_API_KEY)

    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
    ) -> Completion:
        system_instruction, contents = _to_gemini_contents(messages)
        gemini_config = types.GenerateContentConfig(
            tools=cast(Any, _to_gemini_tools(tools) if tools else None),
            system_instruction=system_instruction,
        )
        try:
            response = await asyncio.to_thread(
                self._client.models.generate_content,
                model=config.GEMINI_MODEL,
                contents=cast(Any, contents),
                config=gemini_config,
            )
        except genai_errors.ClientError as exc:
            if exc.code == 404:
                raise AgentConfigurationError(
                    f"GEMINI_MODEL '{config.GEMINI_MODEL}' is not available. Try gemini-2.5-flash."
                ) from exc
            if exc.code in {401, 403}:
                raise AgentConfigurationError("Invalid or unauthorized GEMINI_API_KEY.") from exc
            raise AgentError(f"Gemini API error ({exc.code}): {exc}") from exc
        return _to_completion(response)


def to_llm_tools(tools: list[MCPTool]) -> list[dict[str, Any]]:
    """Convert MCP tool definitions to function-calling metadata."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or tool.title or tool.name,
                "parameters": tool.input_schema or {"type": "object", "properties": {}},
            },
        }
        for tool in tools
    ]


def tool_result_payload(result: CallToolResult) -> str:
    """Serialize an MCP tool result for the next LLM turn."""
    if result.structured_content is not None:
        payload: dict[str, Any] = {"ok": not result.is_error, "data": result.structured_content}
    else:
        text = "\n".join(block.text for block in result.content if isinstance(block, TextContent))
        payload = {"ok": not result.is_error, "message": text or "no content"}
    return json.dumps(payload)


def _to_gemini_tools(tools: list[dict[str, Any]] | None) -> list[types.Tool] | None:
    if not tools:
        return None
    declarations = [
        types.FunctionDeclaration(
            name=item["function"]["name"],
            description=item["function"]["description"],
            parameters_json_schema=_strict_schema(item["function"]["parameters"]),
        )
        for item in tools
    ]
    return [types.Tool(function_declarations=declarations)]


def _to_gemini_contents(messages: list[dict[str, Any]]) -> tuple[str | None, list[types.Content]]:
    system_instruction: str | None = None
    contents: list[types.Content] = []
    tool_names: dict[str, str] = {}

    for message in messages:
        role = message["role"]
        if role == "system":
            system_instruction = message["content"]
            continue
        if role == "user":
            contents.append(types.Content(role="user", parts=[types.Part(text=message["content"])]))
            continue
        if role == "assistant":
            parts: list[types.Part] = []
            if message.get("content"):
                parts.append(types.Part(text=message["content"]))
            for call in message.get("tool_calls") or []:
                function = call["function"]
                tool_names[call["id"]] = function["name"]
                args = json.loads(function.get("arguments") or "{}")
                parts.append(types.Part(function_call=types.FunctionCall(name=function["name"], args=args)))
            contents.append(types.Content(role="model", parts=parts))
            continue
        if role == "tool":
            name = message.get("name") or tool_names.get(message["tool_call_id"])
            if not name:
                raise AgentError("Tool message missing function name")
            payload = json.loads(message["content"])
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part(function_response=types.FunctionResponse(name=name, response=payload))],
                )
            )

    return system_instruction, contents


def _response_text(response: Any) -> str | None:
    """Extract assistant text without using response.text (avoids SDK warnings on tool calls)."""
    parts = response.parts or []
    chunks: list[str] = []
    for part in parts:
        if not isinstance(part.text, str):
            continue
        if isinstance(part.thought, bool) and part.thought:
            continue
        chunks.append(part.text)
    text = "".join(chunks).strip()
    return text or None


def _to_completion(response: Any) -> Completion:
    tool_calls: list[ToolCallPart] = []
    for call in response.function_calls or []:
        tool_calls.append(
            ToolCallPart(
                id=str(uuid.uuid4()),
                function=FunctionCallPart(name=call.name, arguments=json.dumps(call.args)),
            )
        )

    text = _response_text(response)
    return Completion(
        choices=[
            CompletionChoice(
                message=AssistantMessage(
                    content=text,
                    tool_calls=tool_calls or None,
                )
            )
        ]
    )


def _strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(schema)
    if out.get("type") == "object":
        out.setdefault("additionalProperties", False)
        for key, value in (out.get("properties") or {}).items():
            if isinstance(value, dict):
                out["properties"][key] = _strict_schema(value)
    return out
