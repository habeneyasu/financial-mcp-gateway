"""Chat service: Gradio UI + JSON API."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

import gradio as gr
import uvicorn
from fastapi import FastAPI, HTTPException, status
from gradio.themes import Base, GoogleFont

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

_EXAMPLE_PROMPTS = [
    "What is the balance for acc-1?",
    "Show recent transactions for acc-1.",
    "Get account details for acc-2.",
    "List users for customer cust-1.",
]

_CUSTOM_CSS = """
:root {
  --fg-header-bg: #0f172a;
  --fg-header-fg: #f8fafc;
  --fg-accent: #2563eb;
  --fg-muted: #64748b;
  --fg-border: #e2e8f0;
  --fg-surface: #ffffff;
}

.gradio-container {
  max-width: 1280px !important;
  width: min(1280px, 96vw) !important;
  margin: 0 auto !important;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, sans-serif !important;
}

.fg-shell {
  border: 1px solid var(--fg-border);
  border-radius: 16px;
  overflow: hidden;
  background: var(--fg-surface);
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
}

.fg-header {
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
  color: var(--fg-header-fg);
  padding: 1.25rem 1.5rem 1rem;
}

.fg-header-top {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.625rem;
  margin-bottom: 0.5rem;
}

.fg-title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 650;
  letter-spacing: -0.02em;
}

.fg-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.15rem 0.55rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.08);
}

.fg-badge-readonly {
  color: #bbf7d0;
  border-color: rgba(34, 197, 94, 0.35);
  background: rgba(34, 197, 94, 0.12);
}

.fg-badge-mcp {
  color: #bfdbfe;
  border-color: rgba(59, 130, 246, 0.35);
  background: rgba(59, 130, 246, 0.12);
}

.fg-subtitle {
  margin: 0;
  color: #cbd5e1;
  font-size: 0.92rem;
  line-height: 1.45;
}

.fg-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1.25rem;
  margin-top: 0.85rem;
  padding-top: 0.85rem;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
  font-size: 0.78rem;
  color: #94a3b8;
}

.fg-meta strong {
  color: #e2e8f0;
  font-weight: 600;
}

.fg-body {
  padding: 0.75rem 1.25rem 0;
}

.fg-main {
  display: flex;
  flex-direction: column-reverse;
  gap: 0.75rem;
  min-height: 560px;
}

.fg-composer-block {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.fg-chatbot {
  border: 1px solid var(--fg-border) !important;
  border-radius: 12px !important;
  background: #f8fafc !important;
  min-height: 520px;
}

.fg-examples-wrap {
  padding: 0 0.25rem;
}

.fg-examples-wrap .label-wrap p {
  font-size: 0.8rem !important;
  color: var(--fg-muted) !important;
  margin-bottom: 0.35rem !important;
}

.fg-input-row {
  position: sticky;
  bottom: 0;
  padding: 0.75rem 1.25rem 1rem;
  border-top: 1px solid var(--fg-border);
  background: #fff;
}

.fg-composer {
  align-items: center !important;
  flex-wrap: nowrap !important;
  gap: 0.65rem !important;
  border: 1px solid #cbd5e1 !important;
  border-radius: 28px !important;
  padding: 0.45rem 0.55rem 0.45rem 1rem !important;
  background: #ffffff !important;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.06) !important;
  overflow: visible !important;
}

.fg-composer > .form,
.fg-composer > .block {
  flex: 1 1 auto !important;
  min-width: 0 !important;
}

.fg-send-btn {
  flex: 0 0 auto !important;
  width: auto !important;
  min-width: 96px !important;
}

.fg-send-btn,
.fg-send-btn > .wrap,
.fg-send-btn button {
  visibility: visible !important;
  opacity: 1 !important;
}

.fg-composer .fg-input {
  flex: 1 1 auto !important;
}

.fg-composer .fg-input textarea {
  border: none !important;
  border-radius: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
  font-size: 0.98rem !important;
  padding: 0.55rem 0 !important;
  min-height: 44px !important;
}

.fg-composer .fg-input textarea:focus {
  border: none !important;
  box-shadow: none !important;
}

.fg-send-btn button {
  border-radius: 999px !important;
  width: 96px !important;
  min-width: 96px !important;
  min-height: 44px !important;
  font-weight: 650 !important;
  font-size: 0.92rem !important;
  margin: 0 !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  background: linear-gradient(90deg, #1d4ed8 0%, #2563eb 100%) !important;
  color: #ffffff !important;
  border: none !important;
}

.fg-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  margin-top: 0.55rem;
  padding: 0 0.35rem;
}

.fg-hint {
  margin: 0;
  color: var(--fg-muted);
  font-size: 0.78rem;
}

.fg-clear-btn button {
  font-size: 0.82rem !important;
  color: var(--fg-muted) !important;
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;
}

.fg-footer {
  margin: 0.75rem 0 0;
  padding: 0.75rem 1rem 1rem;
  border-top: 1px solid var(--fg-border);
  color: var(--fg-muted);
  font-size: 0.75rem;
  line-height: 1.45;
}

.fg-examples button {
  border-radius: 999px !important;
  font-size: 0.82rem !important;
}
"""


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


def _extract_message_text(content: Any) -> str:
    """Read user/assistant text from Gradio chat history (string or normalized parts)."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str) and item.strip():
                parts.append(item.strip())
            elif isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        return "\n".join(parts).strip()
    return ""


def _messages_to_chat_history(history: list[dict[str, Any]]) -> list[ChatMessage]:
    messages: list[ChatMessage] = []
    for item in history:
        role = item.get("role")
        if role not in {"user", "assistant"}:
            continue
        text = _extract_message_text(item.get("content"))
        if text:
            messages.append(ChatMessage(role=role, content=text))
    return messages


def _append_user_message(
    message: str,
    history: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    text = message.strip()
    if not text:
        return "", history
    return "", history + [{"role": "user", "content": text}]


async def _generate_reply(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not history or history[-1].get("role") != "user":
        return history

    text = _extract_message_text(history[-1].get("content"))
    if not text:
        return history

    try:
        response = await chat(
            ChatRequest(message=text, history=_messages_to_chat_history(history[:-1])),
        )
        reply = response.reply
    except AgentConfigurationError as exc:
        reply = f"Configuration error: {exc}"
    except AgentError as exc:
        reply = f"Agent error: {exc}"
    except Exception:
        logger.exception("gradio chat failed")
        reply = "Something went wrong. Check server logs."

    return history + [{"role": "assistant", "content": reply}]


def _wire_submit(trigger, prompt, chatbot) -> None:
    trigger(
        _append_user_message,
        [prompt, chatbot],
        [prompt, chatbot],
        queue=False,
    ).then(
        _generate_reply,
        [chatbot],
        [chatbot],
        show_progress="minimal",
    )


def _header_html() -> str:
    return f"""
<div class="fg-shell">
  <header class="fg-header">
    <div class="fg-header-top">
      <h1 class="fg-title">Financial MCP Gateway</h1>
      <span class="fg-badge fg-badge-readonly">Read-only</span>
      <span class="fg-badge fg-badge-mcp">MCP-gated</span>
    </div>
    <p class="fg-subtitle">
      Ask questions about customers, accounts, balances, transactions, and users.
      Answers come from MCP tools — not direct database access.
    </p>
    <div class="fg-meta">
      <span><strong>Model</strong> {config.GEMINI_MODEL}</span>
      <span><strong>MCP</strong> {config.mcp_url}</span>
      <span><strong>Tool rounds</strong> ≤ {config.AGENT_MAX_TOOL_ROUNDS}</span>
    </div>
  </header>
"""


def _footer_html() -> str:
    return """
  <p class="fg-footer">
    Reference demo only — not production banking. Do not share real credentials or sensitive data.
    Transfers, writes, and account mutations are not supported.
  </p>
</div>
"""


def _build_theme() -> Base:
    return Base(
        primary_hue="blue",
        secondary_hue="slate",
        neutral_hue="slate",
        font=[GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"],
    ).set(
        body_background_fill="#f1f5f9",
        block_background_fill="#ffffff",
        block_border_width="0px",
        block_label_text_weight="600",
        button_primary_background_fill="linear-gradient(90deg, #1d4ed8 0%, #2563eb 100%)",
        button_primary_background_fill_hover="linear-gradient(90deg, #1e40af 0%, #1d4ed8 100%)",
        button_primary_text_color="#ffffff",
        input_background_fill="#ffffff",
    )


def build_chat_ui() -> gr.Blocks:
    with gr.Blocks(title="Financial MCP Gateway") as demo:
        gr.HTML(_header_html())

        with gr.Column(elem_classes=["fg-body"]):
            with gr.Column(elem_classes=["fg-main"]):
                with gr.Column(elem_classes=["fg-composer-block", "fg-input-row"]):
                    with gr.Row(elem_classes=["fg-composer"]):
                        prompt = gr.Textbox(
                            placeholder="Message Financial MCP Gateway…",
                            lines=1,
                            max_lines=6,
                            show_label=False,
                            container=False,
                            elem_classes=["fg-input"],
                            scale=12,
                        )
                        send = gr.Button(
                            "Send",
                            variant="primary",
                            elem_classes=["fg-send-btn"],
                        )

                    with gr.Row(elem_classes=["fg-toolbar"]):
                        gr.Markdown(
                            "Press **Enter** to send · **Shift+Enter** for a new line",
                            elem_classes=["fg-hint"],
                        )
                        clear = gr.Button(
                            "Clear chat",
                            variant="secondary",
                            elem_classes=["fg-clear-btn"],
                        )

                chatbot = gr.Chatbot(
                    height=520,
                    show_label=False,
                    elem_classes=["fg-chatbot"],
                    layout="bubble",
                    placeholder=(
                        "Ask a financial question to get started.\n\n"
                        "Example: What is the balance for acc-1?"
                    ),
                    feedback_options=None,
                    buttons=["copy"],
                )

                with gr.Column(elem_classes=["fg-examples-wrap"]):
                    gr.Examples(
                        examples=[[item] for item in _EXAMPLE_PROMPTS],
                        inputs=prompt,
                        label="Suggested prompts",
                    )

        gr.HTML(_footer_html())

        _wire_submit(prompt.submit, prompt, chatbot)
        _wire_submit(send.click, prompt, chatbot)
        clear.click(lambda: ([], ""), outputs=[chatbot, prompt])

    return demo


_CHAT_THEME = _build_theme()
_CHAT_UI = build_chat_ui()

gr.mount_gradio_app(
    app,
    _CHAT_UI,
    path="/",
    theme=_CHAT_THEME,
    css=_CUSTOM_CSS,
    footer_links=["api"],
)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    uvicorn.run("chat_app:app", host="0.0.0.0", port=config.CHAT_PORT)


if __name__ == "__main__":
    main()
