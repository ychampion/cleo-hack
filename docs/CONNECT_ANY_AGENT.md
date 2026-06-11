# Connect Any Agent — Bring Your Own MCP Client

Cleo's feedback store is a **standard MCP server** (FastMCP, `mcp_server/server.py`).
Nothing about it is ADK-specific: the same 16+ tools the bundled Gemini agent uses are
exposed over standard MCP transports, so *any* MCP-capable client or provider — Claude
Code, Claude Desktop, Cursor, Gemini CLI, your own SDK script — can read, triage, and
operate the same workspace.

All configs below are copy-paste; replace `/abs/path/to/cleo-hack` with your checkout
path (on Windows use forward slashes in JSON, e.g. `C:/Users/you/cleo-hack`).

---

## 1. Start the server

Two transports cover every client:

```bash
# stdio (the client spawns the process itself — used by most desktop clients)
uv run python -m mcp_server.server

# Streamable HTTP (one long-running server, many clients)
uv run python -m mcp_server.server --transport streamable-http --port 8765
# → endpoint: http://127.0.0.1:8765/mcp
```

`--transport sse` is also available for legacy SSE-only clients (`--host` / `--port`
apply the same way).

> **Working directory matters for stdio.** The SQLite store defaults to the relative
> path `data/cleo.db` (`CLEO_DB_PATH` env). Either make sure the client launches the
> server with the repo root as its working directory (each config below shows how),
> use `uv run --directory /abs/path/to/cleo-hack …` so `uv` resolves the project from
> anywhere, or set `CLEO_DB_PATH` to an absolute path. Otherwise you will get a fresh,
> empty database wherever the client happened to spawn the process.

Seed demo data first if the store is empty: `uv run python -m seed.seed`.

---

## 2. Claude Code

**stdio** (run this *from the cleo-hack repo root* — Claude Code launches local stdio
servers from the directory where they were added):

```bash
claude mcp add cleo -- uv run python -m mcp_server.server
```

Location-independent variant (works no matter where the server is spawned from):

```bash
claude mcp add cleo -- uv run --directory /abs/path/to/cleo-hack python -m mcp_server.server
```

The `--` separates Claude's own flags from the server command; everything after it is
executed verbatim.

**Streamable HTTP** (start the server yourself first, see §1):

```bash
claude mcp add --transport http cleo http://127.0.0.1:8765/mcp
```

**Project-scoped `.mcp.json`** (committed at the repo root; teammates get the server
automatically after approving it):

```json
{
  "mcpServers": {
    "cleo": {
      "command": "uv",
      "args": ["run", "python", "-m", "mcp_server.server"],
      "env": {}
    }
  }
}
```

HTTP form of the same entry — `"type": "streamable-http"` is accepted as an alias for
`"http"`, so MCP-spec naming works unchanged:

```json
{
  "mcpServers": {
    "cleo": {
      "type": "http",
      "url": "http://127.0.0.1:8765/mcp"
    }
  }
}
```

Verify with `claude mcp list`, then ask: *"Use the cleo tools to give me an overview of
the feedback workspace."*

---

## 3. Cursor

`~/.cursor/mcp.json` (global) or `.cursor/mcp.json` in any project. Cursor infers the
transport from the keys: `command`/`args` → stdio, `url` → remote.

```json
{
  "mcpServers": {
    "cleo": {
      "command": "uv",
      "args": ["run", "--directory", "/abs/path/to/cleo-hack", "python", "-m", "mcp_server.server"]
    }
  }
}
```

Or point at a running Streamable HTTP server:

```json
{
  "mcpServers": {
    "cleo": {
      "url": "http://127.0.0.1:8765/mcp"
    }
  }
}
```

---

## 4. Gemini CLI

`~/.gemini/settings.json` (user) or `.gemini/settings.json` (project), under
`mcpServers`. Gemini CLI supports a `cwd` key for stdio servers, which is the cleanest
way to pin the working directory:

```json
{
  "mcpServers": {
    "cleo": {
      "command": "uv",
      "args": ["run", "python", "-m", "mcp_server.server"],
      "cwd": "/abs/path/to/cleo-hack"
    }
  }
}
```

Streamable HTTP uses the dedicated `httpUrl` key (`url` is reserved for SSE servers):

```json
{
  "mcpServers": {
    "cleo": {
      "httpUrl": "http://127.0.0.1:8765/mcp"
    }
  }
}
```

Check the connection inside the CLI with `/mcp`.

---

## 5. Claude Desktop

`claude_desktop_config.json`
(macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`,
Windows: `%APPDATA%\Claude\claude_desktop_config.json`). Claude Desktop only speaks
stdio for local servers and has no `cwd` key, so use `uv --directory` with absolute
paths:

```json
{
  "mcpServers": {
    "cleo": {
      "command": "uv",
      "args": ["run", "--directory", "/abs/path/to/cleo-hack", "python", "-m", "mcp_server.server"]
    }
  }
}
```

If `uv` isn't on Claude Desktop's PATH (common on macOS), use the absolute path to the
`uv` binary as `command`. Restart Claude Desktop after editing the file.

---

## 6. What you can do once connected

A five-minute tour with any connected agent:

| Ask the agent to call… | You get |
|---|---|
| `get_overview` | counts (feedback / untriaged / themes / bets / actions executed), urgent themes, latest brief week |
| `list_feedback` (`only_untriaged: true`) | raw customer feedback awaiting triage |
| `list_themes` | clustered themes with urgency + trend |
| `save_bets` | propose evidence-backed product bets (impact / effort / confidence) |
| `record_action` | log an entry in the autonomous-action ledger |

The full surface is the 16+ tools in `CONTRACTS.md` §2 (plus skills and handoffs
tools as they land): ingest, search, tag, themes, bets, briefs, directives, runs.

**Write tools obey the same ledger discipline as the bundled agent.** Every tool
validates its input against the §1 data shapes and returns
`{"status": "success" | "error", …}`; actions move through the
`record_action` → `complete_action` ledger with rationale and evidence ids. An
external agent operating Cleo leaves exactly the same audit trail in the Actions view
as the built-in operator — there is no privileged side door.

---

## 7. Security note

> **Demo scope — local use only.**
> The server binds `127.0.0.1` by default and has **no authentication layer**: anyone
> who can reach the port (or spawn the stdio process) can read and write the entire
> feedback store. Do not pass `--host 0.0.0.0`, do not port-forward it, and do not
> expose it through a tunnel or reverse proxy on a shared network. If you must reach
> it remotely, keep it loopback-bound and use an authenticated SSH tunnel
> (`ssh -L 8765:127.0.0.1:8765 …`).
