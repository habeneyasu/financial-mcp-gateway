#!/usr/bin/env python3
"""Static MCP security scanner aligned with the financial gateway architecture."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal

SKIP_DIRS = {".venv", ".git", "__pycache__", "dist", "data", "node_modules"}
SELF_FILE = "mcp_guard.py"
CONFIRMED_SECRET_PATTERNS = (
    re.compile(r"""sk-[A-Za-z0-9]{10,}"""),
    re.compile(r"""csk-[A-Za-z0-9]{10,}"""),
    re.compile(r"""AIza[0-9A-Za-z\-_]{20,}"""),
    re.compile(r"""AQ\.[A-Za-z0-9\-_]{20,}"""),
)
POSSIBLE_SECRET_PATTERN = re.compile(
    r"""(?i)(api[_-]?key|secret|password|token)\s*=\s*['"][^'"\s]{8,}['"]"""
)
SENSITIVE_FIELD_NAMES = frozenset(
    {
        "first_name",
        "last_name",
        "email",
        "phone_number",
        "ssn",
        "date_of_birth",
        "account_number",
    }
)
CRITICAL_EXEC = frozenset({"eval", "exec", "os.system", "os.popen"})
DIRECT_DATA_IMPORTS = frozenset({"db", "sqlite3"})
SERVICE_IMPORT_MARKERS = (".service import", "AccountService", "CustomerService", "TransactionService")
SEVERITY_POINTS = {"CRITICAL": 25, "HIGH": 15, "MEDIUM": 8, "LOW": 3}


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


Confidence = Literal["confirmed", "possible", "unverified"]


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: Severity
    title: str
    description: str
    file: str | None = None
    line: int | None = None
    recommendation: str | None = None
    confidence: Confidence = "confirmed"


@dataclass
class ToolDefinition:
    name: str
    file: str
    line: int
    structured_output: bool
    parameters: list[str]


@dataclass
class ModelDefinition:
    name: str
    file: str
    line: int
    fields: set[str]


@dataclass
class RepoLayout:
    root: Path
    files: dict[str, str] = field(default_factory=dict)

    def resolve(self, *candidates: str) -> str | None:
        for candidate in candidates:
            if candidate in self.files:
                return candidate
        normalized = [c.replace("\\", "/") for c in candidates]
        for rel in self.files:
            rel_norm = rel.replace("\\", "/")
            for candidate in normalized:
                if rel_norm == candidate or rel_norm.endswith(f"/{candidate}"):
                    return rel
        return None

    def text(self, *candidates: str) -> str | None:
        rel = self.resolve(*candidates)
        return self.files.get(rel) if rel else None

    def tree(self, *candidates: str) -> ast.Module | None:
        rel = self.resolve(*candidates)
        if not rel:
            return None
        try:
            return ast.parse(self.files[rel])
        except SyntaxError:
            return None

    @classmethod
    def load(cls, root: Path) -> RepoLayout:
        files: dict[str, str] = {}
        for path in sorted(root.rglob("*.py")):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            rel = str(path.relative_to(root))
            if rel == SELF_FILE:
                continue
            files[rel] = path.read_text(encoding="utf-8")
        return cls(root=root.resolve(), files=files)


@dataclass
class ArchitectureCheck:
    layer: str
    status: Literal["ok", "gap", "unverified"]
    detail: str


@dataclass
class Report:
    target: str
    findings: list[Finding]
    architecture: list[ArchitectureCheck]

    @property
    def score(self) -> int:
        penalty = 0
        for finding in self.findings:
            weight = SEVERITY_POINTS[finding.severity.value]
            if finding.confidence == "possible":
                weight = max(3, weight // 2)
            elif finding.confidence == "unverified":
                weight = max(1, weight // 3)
            penalty += weight
        return max(0, min(100, 100 - penalty))

    @property
    def status(self) -> str:
        if any(f.severity == Severity.CRITICAL and f.confidence == "confirmed" for f in self.findings):
            return "FAIL"
        if self.score >= 90:
            return "PASS"
        if self.score >= 70:
            return "REVIEW"
        return "FAIL"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Static MCP security scan")
    parser.add_argument("target", nargs="?", default=".", help="Repository root")
    parser.add_argument("--format", choices=("text", "json", "markdown"), default="text")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fail-on", choices=tuple(s.value.lower() for s in Severity))
    args = parser.parse_args(argv)

    root = Path(args.target).resolve()
    if not root.exists():
        parser.error(f"target does not exist: {root}")

    report = scan(root)
    body = render(report, args.format)
    if args.output:
        args.output.write_text(body + "\n", encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(body)

    if args.fail_on and _has_severity(report, args.fail_on.upper()):
        return 1
    return 1 if report.status == "FAIL" else 0


def scan(root: Path) -> Report:
    repo = RepoLayout.load(root)
    tools = _parse_tools(repo)
    models = _parse_models(repo)
    findings: list[Finding] = []
    findings.extend(_check_secrets(repo))
    findings.extend(_check_dangerous_code(repo))
    findings.extend(_check_auth(repo))
    findings.extend(_check_transport(repo))
    findings.extend(_check_rate_limit(repo))
    findings.extend(_check_guardrails(repo))
    findings.extend(_check_tools(tools, models))
    findings.extend(_check_agent_boundary(repo))
    findings.extend(_check_chat_auth(repo))
    findings.extend(_check_tool_authorization(repo))
    findings.extend(_check_audit(repo))
    architecture = _architecture_checks(repo, findings)
    findings.sort(key=lambda f: (f.severity.value, f.rule_id, f.title))
    return Report(target=str(repo.root), findings=findings, architecture=architecture)


def _check_secrets(repo: RepoLayout) -> list[Finding]:
    findings: list[Finding] = []
    gitignore = repo.root / ".gitignore"
    if not gitignore.exists() or ".env" not in gitignore.read_text(encoding="utf-8"):
        findings.append(
            Finding(
                "MCP001",
                Severity.HIGH,
                "`.env` not gitignored",
                "Environment files may be committed.",
                ".gitignore",
                recommendation="Add `.env` to `.gitignore`.",
            )
        )

    for rel, text in repo.files.items():
        for line_no, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or "os.getenv" in line or "os.environ" in line:
                continue
            if re.search(r"(?i)\bSEED_", line):
                continue

            for pattern in CONFIRMED_SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        Finding(
                            "MCP001",
                            Severity.CRITICAL,
                            "Confirmed secret pattern",
                            "Credential-like value detected in source.",
                            rel,
                            line_no,
                            "Move secrets to environment variables or a secret manager.",
                            confidence="confirmed",
                        )
                    )
                    break
            else:
                if POSSIBLE_SECRET_PATTERN.search(line):
                    findings.append(
                        Finding(
                            "MCP001",
                            Severity.HIGH,
                            "Possible hard-coded secret",
                            "Assignment looks like a secret; verify it is not used in production.",
                            rel,
                            line_no,
                            "Replace with environment configuration.",
                            confidence="possible",
                        )
                    )
    return findings


def _check_dangerous_code(repo: RepoLayout) -> list[Finding]:
    findings: list[Finding] = []
    for rel, text in repo.files.items():
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            target = _call_name(node.func)
            if target in {"eval", "exec"} or target in {"os.system", "os.popen"}:
                findings.append(
                    Finding(
                        "MCP002",
                        Severity.CRITICAL,
                        "Dangerous execution primitive",
                        f"Found `{target}`.",
                        rel,
                        node.lineno,
                        "Remove dynamic execution from MCP-related code paths.",
                    )
                )
            elif target in {"subprocess.run", "subprocess.call", "subprocess.Popen"} and _kw_true(node, "shell"):
                findings.append(
                    Finding(
                        "MCP002",
                        Severity.CRITICAL,
                        "Shell execution enabled",
                        f"Found `{target}(..., shell=True)`.",
                        rel,
                        node.lineno,
                        "Avoid shell=True; use argument lists and strict allowlists.",
                    )
                )
    return findings


def _check_auth(repo: RepoLayout) -> list[Finding]:
    """MCP004: auth cannot be reliably proven from static source alone."""
    server_rel = repo.resolve("server.py")
    server = repo.text("server.py")
    if not server or not server_rel or "mcp.run(" not in server:
        return []

    return [
        Finding(
            "MCP004",
            Severity.LOW,
            "MCP authentication not verifiable statically",
            "This scan does not infer auth from config keys or symbol names. "
            "Confirm MCP client authentication in deployment tests or a live probe.",
            server_rel,
            confidence="unverified",
            recommendation="Add integration tests that reject unauthenticated list_tools/call_tool requests.",
        )
    ]


def _check_transport(repo: RepoLayout) -> list[Finding]:
    findings: list[Finding] = []
    server_rel = repo.resolve("server.py")
    server = repo.text("server.py")
    if not server or not server_rel:
        return findings

    if 'host="0.0.0.0"' in server or "host='0.0.0.0'" in server:
        findings.append(
            Finding(
                "MCP010",
                Severity.MEDIUM,
                "MCP server binds to all interfaces",
                "server.py listens on 0.0.0.0.",
                server_rel,
                recommendation="Use 127.0.0.1 in development and restrict exposure in production.",
            )
        )

    if "streamable-http" in server:
        findings.append(
            Finding(
                "MCP010",
                Severity.LOW,
                "TLS termination not verifiable statically",
                "MCP uses HTTP in server.py; TLS may be handled by a reverse proxy and cannot be confirmed from source alone.",
                server_rel,
                confidence="unverified",
                recommendation="Document TLS termination and verify HTTPS at deployment time.",
            )
        )
    return findings


def _check_rate_limit(repo: RepoLayout) -> list[Finding]:
    server = repo.text("server.py") or ""
    chat = repo.text("chat_app.py") or ""
    combined = (server + chat).lower()
    if any(token in combined for token in ("rate_limit", "slowapi", "limiter")):
        return []
    rel = repo.resolve("server.py") or repo.resolve("chat_app.py")
    return [
        Finding(
            "MCP008",
            Severity.MEDIUM,
            "Missing rate limiting",
            "No rate-limit middleware detected on MCP or chat entrypoints.",
            rel,
            recommendation="Add per-client limits on /mcp and /chat.",
        )
    ]


def _check_guardrails(repo: RepoLayout) -> list[Finding]:
    schema_rel = repo.resolve("src/financial_mcp_gateway/agent/schema.py", "agent/schema.py")
    agent_rel = repo.resolve("src/financial_mcp_gateway/agent/agent.py", "agent/agent.py")
    if not schema_rel:
        return [
            Finding(
                "MCP005",
                Severity.HIGH,
                "Missing API guardrail module",
                "Agent schema/guardrail module not found.",
                recommendation="Add Pydantic request models and input validation before LLM/MCP calls.",
            )
        ]

    schema_tree = ast.parse(repo.files[schema_rel])
    guardrail_fn = _function_names(schema_tree) & {"validate_input", "check_input"}
    has_unsafe_patterns = "_UNSAFE_INPUT" in repo.files[schema_rel]
    has_format_reply = "format_reply" in _function_names(schema_tree) or "build_response" in _function_names(schema_tree)

    findings: list[Finding] = []
    if not guardrail_fn or not has_unsafe_patterns:
        findings.append(
            Finding(
                "MCP005",
                Severity.HIGH,
                "Incomplete input guardrails",
                "Expected validate_input/check_input with unsafe-input pattern checks in schema.py.",
                schema_rel,
                recommendation="Block empty input, prompt injection, and secret-exfiltration attempts before the LLM loop.",
            )
        )
    if not has_format_reply:
        findings.append(
            Finding(
                "MCP005",
                Severity.MEDIUM,
                "Missing output guardrails",
                "No format_reply/build_response helper detected for normalizing model output.",
                schema_rel,
                recommendation="Normalize and truncate assistant output before returning it from /chat.",
            )
        )

    if agent_rel:
        agent_tree = ast.parse(repo.files[agent_rel])
        respond_fn = _first_function(agent_tree, "respond")
        if respond_fn and guardrail_fn:
            called = _called_names(respond_fn) | _called_attributes(respond_fn)
            expected = next(iter(guardrail_fn))
            if expected not in called:
                findings.append(
                    Finding(
                        "MCP005",
                        Severity.HIGH,
                        "Guardrails not wired in agent",
                        f"Agent respond() does not call `{expected}()` before the LLM/tool loop.",
                        agent_rel,
                        recommendation="Invoke input guardrails at the start of respond().",
                    )
                )
    return findings


def _check_tools(tools: list[ToolDefinition], models: list[ModelDefinition]) -> list[Finding]:
    findings: list[Finding] = []
    for tool in tools:
        if not tool.structured_output:
            findings.append(
                Finding(
                    "MCP019",
                    Severity.MEDIUM,
                    "Missing structured tool output",
                    f"Tool `{tool.name}` does not set structured_output=True.",
                    tool.file,
                    tool.line,
                    recommendation="Use structured MCP tool outputs with explicit schemas.",
                )
            )
        if not tool.parameters:
            findings.append(
                Finding(
                    "MCP019",
                    Severity.MEDIUM,
                    "Missing tool parameters",
                    f"Tool `{tool.name}` has no typed input parameters.",
                    tool.file,
                    tool.line,
                    recommendation="Declare typed tool arguments so clients cannot send ambiguous payloads.",
                )
            )

    for model in models:
        sensitive = model.fields & SENSITIVE_FIELD_NAMES
        if len(sensitive) >= 2 or ("first_name" in sensitive and "last_name" in sensitive):
            findings.append(
                Finding(
                    "MCP018",
                    Severity.HIGH,
                    "Excessive sensitive data in tool schema",
                    f"Model `{model.name}` exposes fields: {', '.join(sorted(sensitive))}.",
                    model.file,
                    model.line,
                    recommendation="Minimize PII in MCP tool payloads; fetch identity only through dedicated tools.",
                )
            )
    return findings


def _check_agent_boundary(repo: RepoLayout) -> list[Finding]:
    agent_rel = repo.resolve("src/financial_mcp_gateway/agent/agent.py", "agent/agent.py")
    if not agent_rel:
        return []

    tree = ast.parse(repo.files[agent_rel])
    imports = _imported_roots(tree)
    findings: list[Finding] = []

    if imports & DIRECT_DATA_IMPORTS:
        findings.append(
            Finding(
                "MCP016",
                Severity.HIGH,
                "Agent bypasses MCP boundary",
                f"Agent imports direct data access modules: {', '.join(sorted(imports & DIRECT_DATA_IMPORTS))}.",
                agent_rel,
                recommendation="Route all data access through GatewayMCPClient.call_tool().",
            )
        )

    if any(marker in repo.files[agent_rel] for marker in SERVICE_IMPORT_MARKERS):
        findings.append(
            Finding(
                "MCP016",
                Severity.HIGH,
                "Agent imports domain services directly",
                "Agent layer imports service modules instead of using MCP tools only.",
                agent_rel,
                recommendation="Keep services behind MCP tools; agent should only call the MCP client.",
            )
        )

    if "GatewayMCPClient" not in repo.files[agent_rel] or "call_tool" not in repo.files[agent_rel]:
        findings.append(
            Finding(
                "MCP016",
                Severity.HIGH,
                "Agent missing MCP client usage",
                "Expected GatewayMCPClient and call_tool usage in the agent orchestrator.",
                agent_rel,
                recommendation="Ensure the tool loop calls MCP via GatewayMCPClient only.",
            )
        )
    return findings


def _check_chat_auth(repo: RepoLayout) -> list[Finding]:
    chat_rel = repo.resolve("chat_app.py")
    if not chat_rel:
        return []

    tree = repo.tree("chat_app.py")
    if tree is None:
        return []

    has_route_auth = _tree_has_fastapi_auth(tree)
    if has_route_auth:
        return [
            Finding(
                "MCP015",
                Severity.LOW,
                "Chat authentication not fully verified",
                "Auth dependencies were detected, but static analysis cannot verify enforcement end-to-end.",
                chat_rel,
                confidence="unverified",
                recommendation="Add tests that reject unauthenticated /chat requests.",
            )
        ]

    return [
        Finding(
            "MCP015",
            Severity.HIGH,
            "Unauthenticated chat gateway",
            "chat_app.py exposes /chat without FastAPI auth dependencies.",
            chat_rel,
            recommendation="Authenticate callers on /chat and propagate identity to MCP authorization checks.",
        )
    ]


def _check_tool_authorization(repo: RepoLayout) -> list[Finding]:
    mcp_files = [rel for rel in repo.files if "financial_mcp_gateway/mcp/" in rel.replace("\\", "/") or "/mcp/" in rel.replace("\\", "/")]
    if not mcp_files:
        return []

    markers = ("authorize", "authorization", "caller", "tenant", "customer_scope", "principal")
    if any(any(marker in repo.files[rel].lower() for marker in markers) for rel in mcp_files):
        return [
            Finding(
                "MCP017",
                Severity.LOW,
                "Tool authorization not fully verified",
                "Authorization-related symbols exist, but caller-to-resource checks cannot be confirmed statically.",
                mcp_files[0],
                confidence="unverified",
                recommendation="Verify callers can only access accounts/customers they are authorized for.",
            )
        ]

    return [
        Finding(
            "MCP017",
            Severity.HIGH,
            "Missing tool authorization",
            "MCP tool handlers do not reference caller identity, tenant scope, or authorization checks.",
            repo.resolve("src/financial_mcp_gateway/mcp/helpers.py", "mcp/helpers.py"),
            recommendation="Authorize each tool call against the requested customer/account/resource.",
        )
    ]


def _check_audit(repo: RepoLayout) -> list[Finding]:
    markers = ("audit", "audit_log", "security_log")
    if any(any(marker in text.lower() for marker in markers) for text in repo.files.values()):
        return [
            Finding(
                "MCP020",
                Severity.LOW,
                "Audit trail not fully verified",
                "Audit-related symbols exist, but structured security audit logging cannot be confirmed statically.",
                confidence="unverified",
                recommendation="Emit structured audit events for tool name, caller, target ID, and outcome.",
            )
        ]
    return [
        Finding(
            "MCP020",
            Severity.MEDIUM,
            "Unverified audit trail",
            "No structured audit logging detected for MCP or chat tool invocations.",
            repo.resolve("src/financial_mcp_gateway/mcp/helpers.py", "mcp/helpers.py"),
            recommendation="Log sensitive reads with caller identity and resource IDs.",
        )
    ]


def _architecture_checks(repo: RepoLayout, findings: list[Finding]) -> list[ArchitectureCheck]:
    rule_ids = {finding.rule_id for finding in findings}
    return [
        ArchitectureCheck("Static scanner", "ok", "mcp_guard.py"),
        ArchitectureCheck(
            "API/Pydantic guardrails",
            "gap" if "MCP005" in rule_ids else "ok",
            "validate_input / format_reply in schema.py",
        ),
        ArchitectureCheck(
            "Financial agent",
            "gap" if "MCP016" in rule_ids else "ok",
            "FinancialGatewayAgent via GatewayMCPClient",
        ),
        ArchitectureCheck("Gemini LLM", "ok" if repo.text("src/financial_mcp_gateway/agent/llm.py", "agent/llm.py") else "unverified", "GeminiClient"),
        ArchitectureCheck(
            "MCP client",
            "ok" if repo.resolve("client.py") else "gap",
            "GatewayMCPClient",
        ),
        ArchitectureCheck(
            "Stateless MCP gateway",
            "ok" if repo.resolve("server.py") else "gap",
            "streamable-http MCP server",
        ),
        ArchitectureCheck(
            "Authorized financial tools",
            "gap" if "MCP017" in rule_ids else "ok",
            "MCP tool handlers",
        ),
        ArchitectureCheck("Database", "ok" if repo.resolve("db.py") else "unverified", "SQLite data layer behind services"),
    ]


def _parse_tools(repo: RepoLayout) -> list[ToolDefinition]:
    tools: list[ToolDefinition] = []
    for rel, text in repo.files.items():
        if "mcp/" not in rel.replace("\\", "/"):
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if _decorator_name(decorator) != "tool":
                    continue
                tools.append(
                    ToolDefinition(
                        name=node.name,
                        file=rel,
                        line=node.lineno,
                        structured_output=_decorator_kw_true(decorator, "structured_output"),
                        parameters=[arg.arg for arg in node.args.args if arg.arg != "self"],
                    )
                )
    return tools


def _parse_models(repo: RepoLayout) -> list[ModelDefinition]:
    models: list[ModelDefinition] = []
    rel = repo.resolve("src/financial_mcp_gateway/mcp/schemas.py", "mcp/schemas.py")
    if not rel:
        return models
    tree = ast.parse(repo.files[rel])
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and _inherits_base_model(node):
            fields = {stmt.target.id for stmt in node.body if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)}
            models.append(ModelDefinition(node.name, rel, node.lineno, fields))
    return models


def render(report: Report, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(
            {
                "target": report.target,
                "score": report.score,
                "status": report.status,
                "architecture": [
                    {"layer": item.layer, "status": item.status, "detail": item.detail}
                    for item in report.architecture
                ],
                "findings": [
                    {
                        "rule_id": f.rule_id,
                        "severity": f.severity.value,
                        "confidence": f.confidence,
                        "title": f.title,
                        "description": f.description,
                        "file": f.file,
                        "line": f.line,
                        "recommendation": f.recommendation,
                    }
                    for f in report.findings
                ],
            },
            indent=2,
        )
    if fmt == "markdown":
        lines = [
            "# MCP Security Report",
            "",
            f"**Score:** {report.score}/100 · **Status:** {report.status}",
            "",
            "## Architecture",
            "",
            "| Layer | Status | Detail |",
            "| --- | --- | --- |",
        ]
        for item in report.architecture:
            lines.append(f"| {item.layer} | {item.status} | {item.detail} |")
        lines.extend(["", "## Findings", ""])
        if not report.findings:
            lines.append("_No findings._")
            return "\n".join(lines)
        for finding in report.findings:
            loc = f" (`{finding.file}:{finding.line}`)" if finding.file else ""
            lines.append(
                f"### [{finding.rule_id}] {finding.title}{loc}\n"
                f"- **Severity:** {finding.severity.value}\n"
                f"- **Confidence:** {finding.confidence}\n"
                f"- {finding.description}"
            )
            if finding.recommendation:
                lines.append(f"- **Fix:** {finding.recommendation}")
            lines.append("")
        return "\n".join(lines).rstrip()

    lines = [
        "MCP SECURITY REPORT",
        "═" * 52,
        f"Target: {report.target}",
        f"Score:  {report.score}/100",
        f"Status: {report.status}",
        "",
        "ARCHITECTURE",
        "─" * 52,
    ]
    for item in report.architecture:
        lines.append(f"[{item.status.upper():>10}] {item.layer} — {item.detail}")
    lines.extend(["", "FINDINGS", "─" * 52])
    if not report.findings:
        lines.append("No findings.")
        return "\n".join(lines)
    for index, finding in enumerate(report.findings, 1):
        loc = f" ({finding.file}:{finding.line})" if finding.file else ""
        lines.append(
            f"{index}. [{finding.rule_id}] {finding.severity.value}/{finding.confidence} — {finding.title}{loc}"
        )
        lines.append(f"   {finding.description}")
        if finding.recommendation:
            lines.append(f"   → {finding.recommendation}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _has_severity(report: Report, minimum: str) -> bool:
    order = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    allowed = set(order[: order.index(minimum) + 1])
    return any(finding.severity.value in allowed for finding in report.findings)


def _decorator_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _decorator_kw_true(node: ast.expr, key: str) -> bool:
    if not isinstance(node, ast.Call):
        return False
    return any(
        keyword.arg == key and isinstance(keyword.value, ast.Constant) and keyword.value.value is True
        for keyword in node.keywords
    )


def _call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None


def _kw_true(node: ast.Call, key: str) -> bool:
    return any(
        keyword.arg == key and isinstance(keyword.value, ast.Constant) and keyword.value.value is True
        for keyword in node.keywords
    )


def _function_names(tree: ast.Module) -> set[str]:
    return {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _first_function(tree: ast.Module, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _called_names(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            names.add(node.func.id)
    return names


def _called_attributes(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            names.add(node.func.attr)
    return names


def _imported_roots(tree: ast.Module) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def _tree_has_fastapi_auth(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Depends":
            return True
        if isinstance(node, ast.Attribute) and node.attr in {"HTTPBearer", "APIKeyHeader", "OAuth2PasswordBearer"}:
            return True
    return False


def _inherits_base_model(node: ast.ClassDef) -> bool:
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id == "BaseModel":
            return True
        if isinstance(base, ast.Attribute) and base.attr == "BaseModel":
            return True
    return False


if __name__ == "__main__":
    sys.exit(main())
