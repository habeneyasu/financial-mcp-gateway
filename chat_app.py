"""Chat service: Gradio UI + JSON API."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import gradio as gr
import uvicorn
from fastapi import FastAPI, HTTPException, status

from config import config
from financial_mcp_gateway.agent import (
    AgentConfigurationError,
    AgentError,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    chat,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if not config.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY is unset; chat requests will fail until configured")
    yield


app = FastAPI(title="Financial Gateway Chat", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "model": config.GEMINI_MODEL, "mcp": config.mcp_url}


@app.post("/chat", response_model=ChatResponse, tags=["chat"])
async def post_chat(payload: ChatRequest) -> ChatResponse:
    try:
        return await chat(payload)
    except AgentConfigurationError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except AgentError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except Exception:
        logger.exception("chat failed")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="chat failed") from None


def _history_to_messages(history: list[list[str | None]]) -> list[ChatMessage]:
    messages: list[ChatMessage] = []
    for user_text, assistant_text in history:
        if user_text:
            messages.append(ChatMessage(role="user", content=user_text))
        if assistant_text:
            messages.append(ChatMessage(role="assistant", content=assistant_text))
    return messages


async def _gradio_reply(message: str, history: list[list[str | None]]) -> str:
    try:
        response = await chat(ChatRequest(message=message, history=_history_to_messages(history)))
        return response.reply
    except AgentConfigurationError as exc:
        return f"Configuration error: {exc}"
    except AgentError as exc:
        return f"Agent error: {exc}"
    except Exception:
        logger.exception("gradio chat failed")
        return "Something went wrong. Check server logs."


gr.mount_gradio_app(
    app,
    gr.ChatInterface(
        fn=_gradio_reply,
        title="Financial Gateway Chat",
        description="Read-only lookups for customers, accounts, transactions, users, and idempotency keys.",
        examples=[
            "What is the balance for acc-1?",
            "Show recent transactions for acc-1.",
            "List users for customer cust-1.",
        ],
    ),
    path="/",
)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    uvicorn.run("chat_app:app", host="0.0.0.0", port=config.CHAT_PORT)


if __name__ == "__main__":
    main()
