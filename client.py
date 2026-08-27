"""MCP client for the financial gateway server."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp import Client
from mcp_types import CallToolResult, ListToolsResult

from config import MCP_MODERN_PROTOCOL_VERSION, config

logger = logging.getLogger(__name__)


class GatewayMCPClient:
    """Async MCP client bound to the gateway HTTP endpoint."""

    def __init__(self, url: str | None = None) -> None:
        self.url = url or config.mcp_url
        self._client: Client | None = None

    async def __aenter__(self) -> GatewayMCPClient:
        self._client = Client(self.url, mode=MCP_MODERN_PROTOCOL_VERSION)
        await self._client.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        if self._client is not None:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
            self._client = None

    @property
    def session(self) -> Client:
        if self._client is None:
            raise RuntimeError("GatewayMCPClient is not connected; use 'async with' first")
        return self._client

    async def list_tools(self) -> ListToolsResult:
        logger.debug("list_tools url=%s", self.url)
        return await self.session.list_tools()

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> CallToolResult:
        logger.debug("call_tool name=%s", name)
        return await self.session.call_tool(name, arguments or {})


@asynccontextmanager
async def connect(url: str | None = None) -> AsyncIterator[GatewayMCPClient]:
    async with GatewayMCPClient(url) as client:
        yield client
