import os

from dotenv import load_dotenv

load_dotenv()

MCP_MODERN_PROTOCOL_VERSION = "2026-07-28"


class Config:
    HOST: str = os.getenv("HOST", "localhost")
    PORT: int = int(os.getenv("PORT", "8000"))
    MCP_PATH: str = os.getenv("MCP_PATH", "/mcp")
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/gateway.db")
    AUTH_HOST: str = os.getenv("AUTH_HOST", "localhost")
    AUTH_PORT: int = int(os.getenv("AUTH_PORT", "8080"))
    AUTH_REALM: str = os.getenv("AUTH_REALM", "master")
    OAUTH_CLIENT_ID: str = os.getenv("OAUTH_CLIENT_ID", "")
    OAUTH_CLIENT_SECRET: str = os.getenv("OAUTH_CLIENT_SECRET", "")
    MCP_SCOPE: str = os.getenv("MCP_SCOPE", "mcp:tools")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    CHAT_PORT: int = int(os.getenv("CHAT_PORT", "8001"))
    AGENT_MAX_TOOL_ROUNDS: int = int(os.getenv("AGENT_MAX_TOOL_ROUNDS", "8"))
    MCP_URL: str = os.getenv("MCP_URL", "")

    @property
    def server_url(self) -> str:
        return f"http://{self.HOST}:{self.PORT}"

    @property
    def mcp_url(self) -> str:
        if self.MCP_URL:
            return self.MCP_URL
        host = "127.0.0.1" if self.HOST in {"0.0.0.0", "localhost", "::"} else self.HOST
        return f"http://{host}:{self.PORT}{self.MCP_PATH}"

    @property
    def auth_base_url(self) -> str:
        return f"http://{self.AUTH_HOST}:{self.AUTH_PORT}/realms/{self.AUTH_REALM}/"

config = Config()