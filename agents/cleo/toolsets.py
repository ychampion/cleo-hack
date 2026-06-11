"""MCP toolset factories (CONTRACTS §3) — the ONLY way Cleo touches the world.

Three connectors, all real MCP servers:

- **feedback store** (ours): stdio ``python -m mcp_server.server``. Each agent
  gets its own toolset instance with a least-privilege ``tool_filter`` — an
  ingestor can ``ingest_feedback`` but cannot ``save_bets``; the synthesizer
  can tag/cluster but cannot write GitHub. Separate instances also mean each
  ParallelAgent branch talks to its own stdio subprocess, so concurrent
  branches never contend for one MCP session (SQLite WAL handles the
  multi-process writes).
- **GitHub** (official, real): hosted Streamable-HTTP endpoint with a PAT;
  stdio ``npx @modelcontextprotocol/server-github`` as an explicit opt-in
  fallback (``GITHUB_MCP_STDIO=1``) for networks where the hosted endpoint is
  unreachable. Returns ``None`` when ``GITHUB_TOKEN`` is unset so the agent
  tree composes itself without GitHub instead of crashing.
- **filesystem** (official): stdio server rooted at the seed corpus, filtered
  to read-only tools — the docs ingestor can read transcripts but never write.

Everything is path-robust: the repo root is derived from ``__file__`` (this
file lives at ``agents/cleo/toolsets.py``), never from the process cwd, so
``adk web agents``, uvicorn, and pytest all resolve the same DB/corpus.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import (
    StdioConnectionParams,
    StreamableHTTPConnectionParams,
)
from mcp import StdioServerParameters

REPO_ROOT = Path(__file__).resolve().parents[2]

GITHUB_HOSTED_MCP_URL = "https://api.githubcopilot.com/mcp/"
GITHUB_READ_TOOLS = ["list_issues", "search_issues"]
GITHUB_WRITE_TOOLS = ["create_issue", "add_issue_comment"]


def db_path() -> Path:
    """Absolute path to the SQLite store (CLEO_DB_PATH, default data/cleo.db)."""
    raw = Path(os.environ.get("CLEO_DB_PATH", "data/cleo.db"))
    return raw if raw.is_absolute() else REPO_ROOT / raw


def corpus_dir() -> Path:
    """Absolute path to the seed corpus (CORPUS_DIR, default seed/corpus)."""
    raw = Path(os.environ.get("CORPUS_DIR", "seed/corpus"))
    return raw if raw.is_absolute() else REPO_ROOT / raw


def make_store_toolset(tool_filter: list[str]) -> McpToolset:
    """Stdio toolset for our cleo-feedback-store MCP server (CONTRACTS §2).

    ``tool_filter`` is required on purpose: every agent must declare exactly
    which store tools it needs (least privilege, and smaller tool menus make
    gemini-3.5-flash's tool selection much more reliable).
    """
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=sys.executable,
                args=["-m", "mcp_server.server"],
                cwd=str(REPO_ROOT),
                env={**os.environ, "CLEO_DB_PATH": str(db_path())},
            ),
            timeout=30,
        ),
        tool_filter=tool_filter,
    )


def make_github_toolset(read_only: bool = False) -> McpToolset | None:
    """GitHub MCP toolset (CONTRACTS §3), or None when GITHUB_TOKEN is unset.

    Primary transport is the hosted Streamable-HTTP endpoint (no local node
    needed, PAT in the Authorization header). Set ``GITHUB_MCP_STDIO=1`` to
    use the official stdio server via npx instead — kept as a fallback because
    the hosted endpoint was reachable at build time, but corp proxies may
    block it. Callers must skip ``None`` when assembling tool lists.
    """
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        return None

    tool_filter = (
        GITHUB_READ_TOOLS if read_only else GITHUB_READ_TOOLS + GITHUB_WRITE_TOOLS
    )

    if os.environ.get("GITHUB_MCP_STDIO", "").strip() in ("1", "true", "yes"):
        npx = shutil.which("npx")
        if not npx:
            # No node toolchain: silently degrading would hide a misconfig,
            # but crashing kills the whole agent tree — log and skip GitHub.
            print(
                "[cleo.toolsets] GITHUB_MCP_STDIO set but npx not found; "
                "GitHub connector disabled.",
                file=sys.stderr,
            )
            return None
        return McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=npx,
                    args=["-y", "@modelcontextprotocol/server-github"],
                    env={**os.environ, "GITHUB_PERSONAL_ACCESS_TOKEN": token},
                ),
                timeout=60,
            ),
            tool_filter=tool_filter,
        )

    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=GITHUB_HOSTED_MCP_URL,
            headers={"Authorization": f"Bearer {token}"},
        ),
        tool_filter=tool_filter,
    )


def make_filesystem_toolset() -> McpToolset | None:
    """Read-only filesystem MCP toolset rooted at the seed corpus (§3).

    Used by the docs ingestor for call-transcripts/docs. Returns None when
    npx is unavailable (e.g. CI without node); the docs ingestor's instruction
    tells it how to behave without these tools.
    """
    npx = shutil.which("npx")
    if not npx:
        return None
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=npx,
                args=[
                    "-y",
                    "@modelcontextprotocol/server-filesystem",
                    str(corpus_dir()),
                ],
            ),
            timeout=60,
        ),
        tool_filter=["list_directory", "read_file"],
    )
