"""Shared helpers for MCP tool handlers."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import TypeVar

from mcp.server.mcpserver.exceptions import ToolError

T = TypeVar("T")


def format_amount(value: int | Decimal) -> str:
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    return f"{value / 100:.2f}"


def run_tool(
    fn: Callable[[], T],
    *,
    not_found: tuple[type[Exception], str] | None = None,
) -> T:
    """Run a tool handler and map failures to MCP tool errors."""
    try:
        return fn()
    except Exception as exc:
        if not_found and isinstance(exc, not_found[0]):
            raise ToolError(f"{not_found[1]}: {exc}") from exc
        raise ToolError(str(exc)) from exc
