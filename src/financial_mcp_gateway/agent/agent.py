"""Agent orchestration: guardrails → LLM tool loop → MCP gateway."""

from __future__ import annotations

import json
import logging
from typing import Any

from client import GatewayMCPClient, connect
from config import config
from financial_mcp_gateway.agent.llm import GeminiClient, to_llm_tools, tool_result_payload
from financial_mcp_gateway.agent.prompts import SYSTEM_PROMPT
from financial_mcp_gateway.agent.schema import (
    AgentError,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    format_reply,
    validate_input,
)

logger = logging.getLogger(__name__)


class FinancialGatewayAgent:
    """Run the Gemini tool-calling loop against the MCP gateway."""

    def __init__(self, gateway: GatewayMCPClient) -> None:
        self._gateway = gateway
        self._llm = GeminiClient()
        self._tools: list[dict[str, Any]] | None = None

    async def respond(self, message: str, history: list[ChatMessage] | None = None) -> ChatResponse:
        blocked = validate_input(message)
        if blocked is not None:
            return blocked

        tools = await self._tools_for_model()
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *[{"role": item.role, "content": item.content} for item in history or []],
            {"role": "user", "content": message.strip()},
        ]
        reply = await self._run_tool_loop(messages, tools)
        return format_reply(reply)

    async def _tools_for_model(self) -> list[dict[str, Any]]:
        if self._tools is None:
            listed = await self._gateway.list_tools()
            self._tools = to_llm_tools(listed.tools)
        return self._tools

    async def _run_tool_loop(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> str:
        for _ in range(config.AGENT_MAX_TOOL_ROUNDS):
            completion = await self._llm.complete(messages, tools=tools)
            assistant = completion.choices[0].message
            if not assistant.tool_calls:
                return (assistant.content or "").strip()

            messages.append(assistant.model_dump(exclude_none=True))
            for call in assistant.tool_calls:
                name = call.function.name
                if not name:
                    raise AgentError("Tool call missing name")
                args = json.loads(call.function.arguments or "{}")
                if not isinstance(args, dict):
                    raise AgentError(f"Tool arguments must be an object for {name}")

                logger.info("mcp tool=%s args=%s", name, args)
                result = await self._gateway.call_tool(name, args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": name,
                        "content": tool_result_payload(result),
                    }
                )

        completion = await self._llm.complete(messages)
        return (completion.choices[0].message.content or "").strip()


async def chat(payload: ChatRequest) -> ChatResponse:
    async with connect() as gateway:
        return await FinancialGatewayAgent(gateway).respond(payload.message, payload.history)
