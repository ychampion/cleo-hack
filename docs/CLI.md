# `cleo` CLI

One command line for the whole product — usable by humans (formatted text) and
machine-readable by agents/scripts (`--json`). Installed via `[project.scripts]`,
so after `uv sync` it is available as:

```bash
uv run cleo <command> [options]      # via uv (recommended)
python -m cli.main <command> ...     # identical, no console script needed
```

## Conventions (read this first if you are an agent)

- **`--json`**: every subcommand accepts it. With `--json`, stdout carries
  *only* JSON (a single document, except `triage` which is JSON-lines).
  Without it, output is human-formatted text.
- **Errors**: any runtime failure exits non-zero and prints exactly one JSON
  object to **stderr**: `{"status": "error", "message": "<what went wrong>"}` —
  in both modes. (argparse usage errors keep argparse's plain usage text,
  exit code 2.)
- **Success envelopes** include `"status": "success"`.
- **Env loading**: each command loads `.env` from the current directory first,
  then the repo root; real environment variables always win over both files.
- **DB path**: `CLEO_DB_PATH` (default `data/cleo.db`). A *relative* path is
  resolved against the repo root, so the CLI hits the same SQLite file as the
  server no matter where you invoke it. Pass an absolute path to isolate.
- **Offline by default**: every command works without network or an API key
  **except `cleo triage`**, which is the one LIVE command.

---

## `cleo init`

Create or update `.env` (from `.env.example`, falling back to a built-in
CONTRACTS §8 template), optionally seeding the demo corpus. Idempotent: only
keys whose flags are explicitly passed are written; rerunning without flags
changes nothing. Secret values are **never** echoed back (masked as `***`).

Target directory: `--dir DIR` if given, else the current working directory.

```bash
uv run cleo init --api-key YOUR_KEY --github-repo owner/repo --demo
uv run cleo init --dir /path/to/checkout --model gemini-3.5-flash --json
```

| Flag | .env key |
|---|---|
| `--api-key` | `GOOGLE_API_KEY` (secret, masked) |
| `--github-token` | `GITHUB_TOKEN` (secret, masked) |
| `--github-repo` | `GITHUB_DEMO_REPO` |
| `--model` | `CLEO_MODEL` |
| `--demo` | runs the idempotent corpus seeder (`seed.seed`, offline) |

`--json` shape:

```json
{
  "status": "success",
  "env_path": "C:\\path\\to\\.env",
  "created": true,
  "updated": ["GOOGLE_API_KEY", "GITHUB_DEMO_REPO"],
  "values": {"GOOGLE_API_KEY": "***", "GITHUB_DEMO_REPO": "owner/repo"},
  "seed": {
    "corpus_items": 88, "ingested": 88, "duplicates": 0,
    "feedback_total": 88, "directives": 2, "db_path": "..."
  }
}
```

(`seed` present only with `--demo`. `values` shows masked/plain values for the
keys written *this run* only.)

---

## `cleo serve`

Run the full API + UI server (`uvicorn app.main:app`). Long-running.

```bash
uv run cleo serve                 # http://127.0.0.1:8080
uv run cleo serve --port 9000 --host 0.0.0.0
```

`--json`: prints one startup line `{"status":"success","command":"serve","url":"http://127.0.0.1:8080"}`
to stdout before launching; uvicorn logs follow on stderr.

---

## `cleo mcp`

Run the `cleo-feedback-store` MCP server (16+ tools). Behavior is identical to
`python -m mcp_server.server` (the CLI delegates to it). Long-running.

```bash
uv run cleo mcp                                   # stdio (for MCP clients)
uv run cleo mcp --transport streamable-http --port 8765   # endpoint at /mcp
uv run cleo mcp --transport sse --host 127.0.0.1 --port 8765
```

stdio mode prints nothing to stdout except the MCP wire protocol — safe to use
directly in `claude mcp add` / `.mcp.json` configs (see docs/CONNECT_ANY_AGENT.md).

---

## `cleo status`

Runtime status **without a server**: model id, key presence, db path, counts.

```bash
uv run cleo status --json
```

```json
{
  "status": "success",
  "model": "gemini-3.5-flash",
  "google_api_key_present": false,
  "github_token_present": false,
  "db_path": "C:\\repo\\data\\cleo.db",
  "db_exists": true,
  "feedback_count": 88,
  "skills_count": 5,
  "store_ready": true
}
```

`store_ready` is `false` (with `feedback_count: 0`) when the store module
cannot be imported — the command still succeeds so scripts can probe health.

---

## `cleo overview`

Workspace overview (the MCP `get_overview` tool result): counts, urgent
themes (urgency >= 2), latest brief week.

```bash
uv run cleo overview --json
```

```json
{
  "status": "success",
  "counts": {"feedback": 88, "untriaged": 88, "themes": 0, "bets": 0, "actions_executed": 0},
  "urgent": [{"id": "th_…", "title": "…", "urgency": 3}],
  "latest_brief_week": "2026-W24"
}
```

---

## `cleo skills list` / `cleo skills show <name>`

Procedural skills the agents consult (authored + learned; root overridable via
`CLEO_SKILLS_DIR`).

```bash
uv run cleo skills list --json
uv run cleo skills show triage-feedback --json
```

`list` shape:

```json
{"status": "success", "skills": [
  {"name": "triage-feedback", "description": "…", "source": "authored"}
]}
```

`show` shape (errors with exit 1 + stderr JSON when the name is unknown):

```json
{"status": "success", "name": "triage-feedback", "description": "…", "body": "…markdown procedure…"}
```

---

## `cleo handoffs list [--status open|in_progress|done|failed]`

Coder work orders (CONTRACTS §12 shape).

```bash
uv run cleo handoffs list --status open --json
```

```json
{"status": "success", "handoffs": [
  {"id": "hf_…", "bet_id": null, "title": "…", "problem": "…",
   "evidence_ids": [], "acceptance": ["…"], "status": "open",
   "result": {"files_changed": [], "tests": "", "notes": ""},
   "created_at": "…", "finished_at": null}
]}
```

---

## `cleo triage [--message TEXT]` — LIVE

Runs the real agent (programmatic ADK Runner on `agents.cleo.agent.root_agent`,
in-memory session) and **streams events as they happen**. Requires
`GOOGLE_API_KEY` (or Vertex env); exits 1 with a clear hint when missing.
Default message: `"Run a full triage of all feedback now."`.

```bash
uv run cleo triage
uv run cleo triage --message "Triage only GitHub feedback" --json
```

`--json` mode is **JSON-lines**: one object per line, shape
`{"agent": "...", "type": "...", "tool"?: "...", "args"?: {...}, "text"?: "..."}`:

| `type` | meaning | extra keys |
|---|---|---|
| `tool_call` | agent invoked a tool | `tool`, `args` |
| `tool_result` | tool returned | `tool`, `text` (compact JSON, truncated at 400 chars) |
| `text` | intermediate model text | `text` |
| `final` | a final response of an agent | `text` |

Human mode prints the same stream as concise prefixed lines
(`-> tool call`, `<- tool result`, `== final text`). Non-zero exit if the run
raises; the error object lands on stderr as usual.

---

## `cleo --version`

Prints `cleo <version>` from package metadata (`cleo-hack` distribution).

## Exit codes

| code | meaning |
|---|---|
| 0 | success |
| 1 | runtime failure (JSON error object on stderr) |
| 2 | argparse usage error (plain usage text) |
| 130 | interrupted (Ctrl+C during `triage`) |
