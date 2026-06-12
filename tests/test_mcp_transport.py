"""Real MCP transport round-trips for the provider-agnostic surface (CONTRACTS §10).

These tests exercise the actual wire protocols any external client would use:
- stdio: spawn `python -m mcp_server.server` exactly like Claude Code / Cursor would.
- streamable-http: boot the server subprocess on a free loopback port and connect
  with the SDK's streamablehttp_client, like `claude mcp add --transport http`.

Loopback only — no external network, no LLM. Each test gets its own tmp SQLite db
via CLEO_DB_PATH, so round-trips run against an empty but fully functional store.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    try:
        # mcp >= 1.27 name; the old spelling is deprecated but yields the same
        # (read, write, get_session_id) triple, so fall back for older SDKs.
        from mcp.client.streamable_http import streamable_http_client
    except ImportError:
        from mcp.client.streamable_http import (
            streamablehttp_client as streamable_http_client,
        )
except ImportError:  # pragma: no cover - environment without the mcp client SDK
    pytest.skip(
        "mcp client modules (mcp.client.stdio / mcp.client.streamable_http) not installed",
        allow_module_level=True,
    )

REPO_ROOT = Path(__file__).resolve().parents[1]

# Per-test budget; both transports together must stay well under ~30s total.
TRANSPORT_TIMEOUT_S = 20.0

# CONTRACTS §2 tool names, plus the §10 convenience read tool, plus the §11/§12
# extension tools. The extension entries guard a real regression: under
# `python -m mcp_server.server` the file executes as __main__ while extensions
# register on the canonical module instance — main() must serve the canonical
# instance or external clients silently lose skills + handoffs.
CONTRACT_TOOLS = {
    "ingest_feedback", "list_feedback", "search_feedback", "tag_feedback",
    "save_themes", "list_themes", "save_bets", "list_bets",
    "record_action", "complete_action", "list_actions",
    "write_brief", "get_latest_brief", "get_directives",
    "start_run", "finish_run",
    "get_overview",
    "list_skills", "load_skill", "save_skill",
    "create_handoff", "get_handoff", "list_handoffs", "update_handoff",
}


def _server_env(tmp_path: Path) -> dict[str, str]:
    """Inherit the parent env (PATH, venv, SYSTEMROOT on Windows) + isolated db."""
    return {**os.environ, "CLEO_DB_PATH": str(tmp_path / "cleo.db")}


def _tool_payload(result) -> dict:
    """Decode a CallToolResult into the plain dict the tool function returned."""
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict) and "status" in structured:
        return structured
    text = "".join(
        block.text for block in result.content if getattr(block, "type", "") == "text"
    )
    return json.loads(text)


async def test_stdio_round_trip(tmp_path):
    """initialize → list_tools (§2 names + get_overview) → call get_overview over stdio."""
    params = StdioServerParameters(
        command=sys.executable,  # never "python": resolves wrong/absent on Windows
        args=["-m", "mcp_server.server"],
        cwd=str(REPO_ROOT),
        env=_server_env(tmp_path),
    )
    async with asyncio.timeout(TRANSPORT_TIMEOUT_S):
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools = await session.list_tools()
                names = {tool.name for tool in tools.tools}
                missing = CONTRACT_TOOLS - names
                assert not missing, f"contract tools missing over stdio: {sorted(missing)}"

                result = await session.call_tool("get_overview", {})
                payload = _tool_payload(result)
                assert payload["status"] == "success"
                assert payload["counts"]["feedback"] == 0  # fresh tmp db
                assert payload["urgent"] == []


async def test_streamable_http_round_trip(tmp_path):
    """Boot --transport streamable-http on a free port, then a full client round-trip."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    log_path = tmp_path / "server.log"
    with open(log_path, "wb") as log:
        proc = subprocess.Popen(
            [
                sys.executable, "-m", "mcp_server.server",
                "--transport", "streamable-http",
                "--host", "127.0.0.1",
                "--port", str(port),
            ],
            cwd=str(REPO_ROOT),
            env=_server_env(tmp_path),
            stdout=log,
            stderr=log,
        )
    try:
        await _wait_until_connectable(port, proc, log_path)

        async with asyncio.timeout(TRANSPORT_TIMEOUT_S):
            url = f"http://127.0.0.1:{port}/mcp"
            async with streamable_http_client(url) as (read, write, _get_session_id):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    tools = await session.list_tools()
                    names = {tool.name for tool in tools.tools}
                    missing = CONTRACT_TOOLS - names
                    assert not missing, f"contract tools missing over http: {sorted(missing)}"

                    result = await session.call_tool("list_feedback", {"limit": 1})
                    payload = _tool_payload(result)
                    assert payload["status"] == "success"
                    assert payload["items"] == []  # fresh tmp db
    finally:
        # Windows has no SIGTERM-style graceful kill for uvicorn; kill() is the
        # reliable cross-platform teardown for a loopback demo server.
        proc.kill()
        proc.wait(timeout=10)


async def _wait_until_connectable(port: int, proc: subprocess.Popen, log_path: Path) -> None:
    """Poll the loopback port until the server accepts TCP, or fail with its log tail."""
    deadline = asyncio.get_running_loop().time() + TRANSPORT_TIMEOUT_S
    while True:
        if proc.poll() is not None:
            raise RuntimeError(
                f"server exited early (code {proc.returncode}): {_log_tail(log_path)}"
            )
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            if asyncio.get_running_loop().time() > deadline:
                raise TimeoutError(
                    f"server not connectable on 127.0.0.1:{port} within "
                    f"{TRANSPORT_TIMEOUT_S}s: {_log_tail(log_path)}"
                ) from None
            await asyncio.sleep(0.25)


def _log_tail(log_path: Path, limit: int = 2000) -> str:
    try:
        return log_path.read_text(encoding="utf-8", errors="replace")[-limit:]
    except OSError:
        return "<no server log captured>"
