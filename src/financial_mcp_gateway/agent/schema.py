"""Chat API models and hard guardrails (enforced in code before/after the LLM)."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

MAX_MESSAGE_CHARS = 4000
MAX_REPLY_CHARS = 4000
MAX_HISTORY = 50

_UNSAFE_INPUT = (
    re.compile(r"(?i)\b(ignore|forget|disregard)\b.{0,40}\b(instruction|prompt|rule)s?\b"),
    re.compile(r"(?i)\b(reveal|show|print|dump)\b.{0,30}\b(system prompt|api key|secret|password)\b"),
)


class AgentError(Exception):
    """Agent orchestration failed."""


class AgentConfigurationError(AgentError):
    """Required agent configuration is missing."""


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    history: list[ChatMessage] = Field(default_factory=list, max_length=MAX_HISTORY)

    @field_validator("message", mode="before")
    @classmethod
    def strip_message(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class ChatResponse(BaseModel):
    status: Literal["answered", "blocked"]
    reply: str = Field(min_length=1)


def validate_input(message: str) -> ChatResponse | None:
    """Return a blocked response when input fails guardrails."""
    text = message.strip()
    if not text:
        return ChatResponse(
            status="blocked",
            reply="Please enter a question about the financial gateway.",
        )

    if any(pattern.search(text) for pattern in _UNSAFE_INPUT):
        return ChatResponse(
            status="blocked",
            reply="I cannot override instructions or share credentials and internal prompts.",
        )

    return None


def format_reply(text: str) -> ChatResponse:
    """Normalize model output into an API response."""
    body = text.strip()
    if not body:
        return ChatResponse(
            status="answered",
            reply=(
                "I couldn't produce a response. Please ask about customers, accounts, "
                "transactions, or users."
            ),
        )

    if len(body) > MAX_REPLY_CHARS:
        body = body[: MAX_REPLY_CHARS - 3].rstrip() + "..."

    return ChatResponse(status="answered", reply=body)
