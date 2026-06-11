"""``cleo`` command line — humans get formatted text, agents get ``--json``.

Design rules (documented in docs/CLI.md, enforced here):

- stdlib argparse only; ZERO new dependencies.
- Every subcommand takes ``--json``: pure machine-readable JSON on stdout,
  nothing else. Human mode prints formatted text instead.
- Failures exit non-zero and print ONE JSON error object to stderr
  (``{"status": "error", "message": "..."}``) in both modes, so scripts can
  always parse stderr. argparse usage errors keep argparse's native text
  (exit 2) — those are developer-facing, not runtime failures.
- Read commands (status/overview/skills/handoffs) import only the store-side
  modules; ``triage`` imports ADK/google lazily INSIDE the command so every
  other subcommand works without agent deps loaded or a GOOGLE_API_KEY set.
- Env: ``.env`` is loaded from the current directory first, then the repo
  root (first definition wins; real environment variables always win over
  both). A relative ``CLEO_DB_PATH`` is resolved against the repo root so
  the CLI hits the same SQLite file as the server regardless of cwd.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any, Callable, NoReturn

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "gemini-3.5-flash"
DEFAULT_DB_PATH = "data/cleo.db"
DEFAULT_TRIAGE_MESSAGE = "Run a full triage of all feedback now."

# Keys `cleo init` manages, in .env order. (key, flag dest, secret?)
ENV_KEYS = (
    ("GOOGLE_API_KEY", "api_key", True),
    ("GITHUB_TOKEN", "github_token", True),
    ("GITHUB_DEMO_REPO", "github_repo", False),
    ("CLEO_MODEL", "model", False),
)

# Fallback .env template (CONTRACTS §8) for when no .env.example is reachable
# (e.g. the package was installed from a wheel, away from the repo checkout).
ENV_TEMPLATE = """\
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY=
CLEO_MODEL=gemini-3.5-flash
CLEO_DB_PATH=data/cleo.db
CORPUS_DIR=seed/corpus
GITHUB_TOKEN=
GITHUB_DEMO_REPO=
"""


# -- plumbing -----------------------------------------------------------------


def _fail(message: str, code: int = 1) -> NoReturn:
    """Exit non-zero with a single JSON error object on stderr (both modes)."""
    print(json.dumps({"status": "error", "message": message}), file=sys.stderr)
    raise SystemExit(code)


def _check(result: Any) -> dict:
    """Pass through a tool result dict, converting {"status":"error"} to exit 1."""
    if not isinstance(result, dict):
        _fail(f"unexpected tool result: {result!r}")
    if result.get("status") == "error":
        _fail(str(result.get("message", "unknown error")))
    return result


def _emit(payload: dict, as_json: bool, human: Callable[[dict], None]) -> None:
    """One payload, two renderings: JSON document or human-formatted lines."""
    if as_json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        human(payload)


def _load_env() -> None:
    """Load .env (cwd first, then repo root); real env vars always win."""
    from dotenv import load_dotenv  # dependency of the project already

    load_dotenv(Path.cwd() / ".env", override=False)
    load_dotenv(REPO_ROOT / ".env", override=False)


def _resolve_db_env() -> Path:
    """Pin CLEO_DB_PATH to an absolute path (relative paths anchor at the repo
    root, matching the server's behavior when launched from the repo) so the
    CLI reads/writes the same SQLite file from any cwd."""
    raw = Path(os.environ.get("CLEO_DB_PATH") or DEFAULT_DB_PATH)
    resolved = raw if raw.is_absolute() else REPO_ROOT / raw
    os.environ["CLEO_DB_PATH"] = str(resolved)
    return resolved


def _version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("cleo-hack")
    except PackageNotFoundError:
        return "0.0.0+uninstalled"


# -- init ----------------------------------------------------------------------


def _read_env_lines(env_path: Path) -> list[str]:
    return env_path.read_text(encoding="utf-8").splitlines()


def _set_env_line(lines: list[str], key: str, value: str) -> list[str]:
    """Replace the ``KEY=…`` line (or append one). Exact-key match only."""
    prefix = f"{key}="
    for i, line in enumerate(lines):
        if line.strip().startswith(prefix):
            lines[i] = f"{key}={value}"
            return lines
    lines.append(f"{key}={value}")
    return lines


def cmd_init(args: argparse.Namespace) -> None:
    target = Path(args.dir).resolve() if args.dir else Path.cwd()
    if not target.is_dir():
        _fail(f"--dir {str(target)!r} is not a directory")
    env_path = target / ".env"

    created = False
    if env_path.exists():
        lines = _read_env_lines(env_path)
    else:
        template = None
        for candidate in (target / ".env.example", REPO_ROOT / ".env.example"):
            if candidate.is_file():
                template = candidate.read_text(encoding="utf-8")
                break
        lines = (template or ENV_TEMPLATE).splitlines()
        created = True

    # Only keys whose flags were EXPLICITLY passed are touched — this is the
    # entire idempotency contract: rerunning without flags changes nothing.
    updated: list[str] = []
    masked: dict[str, str] = {}
    for key, dest, secret in ENV_KEYS:
        value = getattr(args, dest)
        if value is None:
            continue
        lines = _set_env_line(lines, key, value)
        updated.append(key)
        masked[key] = "***" if secret else value

    env_path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")

    seed_summary: dict | None = None
    if args.demo:
        # Honor the .env we just wrote (db path, corpus dir) without clobbering
        # anything already in the real environment.
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)
        _resolve_db_env()
        try:
            from seed.seed import main as seed_main
        except ImportError as exc:
            _fail(f"seeder not available (seed.seed): {exc}")
        try:
            # The seeder prints a human summary line; capture it so --json
            # stdout stays pure. Its return dict is the machine answer.
            with redirect_stdout(io.StringIO()):
                seed_summary = seed_main()
        except SystemExit as exc:
            _fail(f"demo seed failed: {exc}")

    payload: dict[str, Any] = {
        "status": "success",
        "env_path": str(env_path),
        "created": created,
        "updated": updated,
        "values": masked,
    }
    if seed_summary is not None:
        payload["seed"] = seed_summary

    def human(p: dict) -> None:
        verb = "created" if p["created"] else "found"
        print(f".env {verb} at {p['env_path']}")
        for key in p["updated"]:
            print(f"  set {key}={p['values'][key]}")
        if not p["updated"]:
            print("  no values changed (pass flags to set them)")
        if "seed" in p:
            s = p["seed"]
            print(
                f"demo seed: {s['ingested']} new feedback items "
                f"({s['duplicates']} duplicates skipped); "
                f"{s['feedback_total']} total; db={s['db_path']}"
            )

    _emit(payload, args.json, human)


# -- serve / mcp -----------------------------------------------------------------


def cmd_serve(args: argparse.Namespace) -> None:
    _load_env()
    _resolve_db_env()
    try:
        import uvicorn
    except ImportError as exc:
        _fail(f"uvicorn not installed: {exc}")
    if args.json:
        print(
            json.dumps(
                {
                    "status": "success",
                    "command": "serve",
                    "url": f"http://{args.host}:{args.port}",
                }
            ),
            flush=True,
        )
    else:
        print(f"cleo serve: http://{args.host}:{args.port} (Ctrl+C to stop)")
    # String import path so app.main's own startup (env, db dir) runs inside
    # uvicorn exactly as `uv run uvicorn app.main:app` would.
    uvicorn.run("app.main:app", host=args.host, port=args.port)


def cmd_mcp(args: argparse.Namespace) -> None:
    _load_env()
    _resolve_db_env()
    try:
        from mcp_server.server import main as mcp_main
    except ImportError as exc:
        _fail(f"mcp_server not available: {exc}")
    # Delegate via argv so behavior (defaults, transports, settings) stays
    # byte-identical with `python -m mcp_server.server`. No stdout banner:
    # stdio transport owns stdout for the MCP wire protocol.
    sys.argv = [
        "cleo-mcp",
        "--transport", args.transport,
        "--host", args.host,
        "--port", str(args.port),
    ]
    if not args.json and args.transport != "stdio":
        print(
            f"cleo mcp: {args.transport} on {args.host}:{args.port}",
            file=sys.stderr,
        )
    mcp_main()


# -- status / overview --------------------------------------------------------


def cmd_status(args: argparse.Namespace) -> None:
    _load_env()
    db_path = _resolve_db_env()

    feedback_count = 0
    store_ready = False
    try:
        from mcp_server.server import get_store

        feedback_count = get_store().count("feedback")
        store_ready = True
    except Exception:  # store module missing / db unreadable — degrade, don't die
        pass

    skills_count = 0
    try:
        from mcp_server.skill_tools import skills_index

        skills_count = len(skills_index())
    except Exception:
        pass

    payload = {
        "status": "success",
        "model": os.environ.get("CLEO_MODEL", DEFAULT_MODEL),
        "google_api_key_present": bool(os.environ.get("GOOGLE_API_KEY", "").strip()),
        "github_token_present": bool(os.environ.get("GITHUB_TOKEN", "").strip()),
        "db_path": str(db_path),
        "db_exists": db_path.is_file(),
        "feedback_count": feedback_count,
        "skills_count": skills_count,
        "store_ready": store_ready,
    }

    def human(p: dict) -> None:
        def flag(b: bool) -> str:
            return "yes" if b else "no"

        print(f"model               {p['model']}")
        print(f"google api key      {flag(p['google_api_key_present'])}")
        print(f"github token        {flag(p['github_token_present'])}")
        print(f"db path             {p['db_path']}{'' if p['db_exists'] else '  (not created yet)'}")
        print(f"feedback items      {p['feedback_count']}")
        print(f"skills              {p['skills_count']}")
        if not p["store_ready"]:
            print("store               UNAVAILABLE (mcp_server import failed)")

    _emit(payload, args.json, human)


def cmd_overview(args: argparse.Namespace) -> None:
    _load_env()
    _resolve_db_env()
    try:
        from mcp_server.server import get_overview
    except ImportError as exc:
        _fail(f"mcp_server not available: {exc}")
    payload = _check(get_overview())

    def human(p: dict) -> None:
        c = p["counts"]
        print(
            f"feedback {c['feedback']} ({c['untriaged']} untriaged) | "
            f"themes {c['themes']} | bets {c['bets']} | "
            f"actions executed {c['actions_executed']}"
        )
        if p["urgent"]:
            print("urgent themes:")
            for t in p["urgent"]:
                print(f"  [{t['urgency']}] {t['id']}  {t['title']}")
        else:
            print("urgent themes: none")
        print(f"latest brief week: {p['latest_brief_week'] or 'none'}")

    _emit(payload, args.json, human)


# -- skills ----------------------------------------------------------------------


def _skill_tools():
    try:
        import mcp_server.skill_tools as skill_tools
    except ImportError as exc:
        _fail(f"skills module not available (mcp_server.skill_tools): {exc}")
    return skill_tools


def cmd_skills_list(args: argparse.Namespace) -> None:
    _load_env()
    _resolve_db_env()
    payload = _check(_skill_tools().list_skills())

    def human(p: dict) -> None:
        skills = p["skills"]
        if not skills:
            print("no skills found")
            return
        width = max(len(s["name"]) for s in skills)
        for s in skills:
            print(f"{s['name']:<{width}}  [{s['source']}]  {s['description']}")

    _emit(payload, args.json, human)


def cmd_skills_show(args: argparse.Namespace) -> None:
    _load_env()
    _resolve_db_env()
    payload = _check(_skill_tools().load_skill(args.name))

    def human(p: dict) -> None:
        print(f"# {p['name']}")
        if p["description"]:
            print(f"# {p['description']}")
        print()
        print(p["body"])

    _emit(payload, args.json, human)


# -- handoffs ---------------------------------------------------------------------


def cmd_handoffs_list(args: argparse.Namespace) -> None:
    _load_env()
    _resolve_db_env()
    try:
        from mcp_server.handoff_tools import list_handoffs
    except ImportError as exc:
        _fail(f"handoffs module not available (mcp_server.handoff_tools): {exc}")
    payload = _check(list_handoffs(status=args.status or ""))

    def human(p: dict) -> None:
        handoffs = p["handoffs"]
        if not handoffs:
            print("no handoffs" + (f" with status {args.status!r}" if args.status else ""))
            return
        for h in handoffs:
            files = len((h.get("result") or {}).get("files_changed") or [])
            print(f"{h['id']}  [{h['status']}]  {h['title']}  (files changed: {files})")

    _emit(payload, args.json, human)


# -- triage (LIVE: needs GOOGLE_API_KEY) -------------------------------------------


def _triage_events(event: Any) -> list[dict[str, Any]]:
    """Flatten one ADK event into the CLI's {agent, type, tool?, args?, text?} lines."""
    agent = getattr(event, "author", "") or "agent"
    content = getattr(event, "content", None)
    parts = getattr(content, "parts", None) or []
    final = bool(getattr(event, "is_final_response", lambda: False)())
    lines: list[dict[str, Any]] = []
    for part in parts:
        fc = getattr(part, "function_call", None)
        if fc is not None:
            lines.append(
                {"agent": agent, "type": "tool_call", "tool": fc.name, "args": dict(fc.args or {})}
            )
            continue
        fr = getattr(part, "function_response", None)
        if fr is not None:
            summary = json.dumps(fr.response, default=str)
            if len(summary) > 400:
                summary = summary[:400] + "…"
            lines.append(
                {"agent": agent, "type": "tool_result", "tool": fr.name, "text": summary}
            )
            continue
        text = getattr(part, "text", None)
        if text:
            lines.append(
                {"agent": agent, "type": "final" if final else "text", "text": text}
            )
    return lines


def cmd_triage(args: argparse.Namespace) -> None:
    _load_env()
    _resolve_db_env()

    use_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").strip().upper() in ("TRUE", "1")
    if not os.environ.get("GOOGLE_API_KEY", "").strip() and not use_vertex:
        _fail(
            "GOOGLE_API_KEY is not set. Add it to .env (cleo init --api-key YOUR_KEY) "
            "or export it, then retry. `cleo triage` is the one LIVE command — "
            "everything else works offline."
        )

    # Lazy imports: ADK + the agent tree load models/toolsets at import time;
    # keeping them inside this command keeps every other subcommand dep-free.
    try:
        import asyncio

        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types

        from agents.cleo.agent import root_agent
    except Exception as exc:  # ImportError or agent-construction failure
        _fail(f"could not load the Cleo agent (google-adk + agents/): {exc}")

    message = args.message or DEFAULT_TRIAGE_MESSAGE
    session_service = InMemorySessionService()
    asyncio.run(
        session_service.create_session(app_name="cleo", user_id="operator", session_id="cli")
    )
    runner = Runner(agent=root_agent, app_name="cleo", session_service=session_service)
    content = types.Content(role="user", parts=[types.Part(text=message)])

    if not args.json:
        print(f"triage: {message}")
    try:
        for event in runner.run(user_id="operator", session_id="cli", new_message=content):
            for line in _triage_events(event):
                if args.json:
                    print(json.dumps(line, default=str), flush=True)
                elif line["type"] == "tool_call":
                    print(f"-> [{line['agent']}] {line['tool']}({json.dumps(line['args'], default=str)})", flush=True)
                elif line["type"] == "tool_result":
                    print(f"<- [{line['agent']}] {line['tool']} {line['text']}", flush=True)
                elif line["type"] == "final":
                    print(f"== [{line['agent']}] {line['text'].strip()}", flush=True)
                else:
                    print(f"   [{line['agent']}] {line['text'].strip()}", flush=True)
    except KeyboardInterrupt:
        _fail("triage interrupted", code=130)
    except Exception as exc:
        hint = ""
        if "API key" in str(exc) or "API_KEY" in str(exc):
            hint = " (is GOOGLE_API_KEY valid?)"
        _fail(f"triage run failed: {exc}{hint}")


# -- parser ----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--json", action="store_true", help="machine-readable JSON on stdout"
    )

    parser = argparse.ArgumentParser(
        prog="cleo",
        description="Cleo — autonomous product-feedback operator (CLI for humans and agents).",
    )
    parser.add_argument(
        "--version", action="version", version=f"cleo {_version()}"
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")

    p = sub.add_parser(
        "init", parents=[common],
        help="create/update .env (and optionally seed the demo corpus)",
    )
    p.add_argument("--dir", help="directory for the .env file (default: current directory)")
    p.add_argument("--api-key", dest="api_key", help="GOOGLE_API_KEY value")
    p.add_argument("--github-token", dest="github_token", help="GITHUB_TOKEN value")
    p.add_argument("--github-repo", dest="github_repo", help="GITHUB_DEMO_REPO (owner/repo)")
    p.add_argument("--model", dest="model", help=f"CLEO_MODEL (default {DEFAULT_MODEL})")
    p.add_argument("--demo", action="store_true", help="seed the demo corpus (offline, idempotent)")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("serve", parents=[common], help="run the API + UI server (uvicorn app.main:app)")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--host", default="127.0.0.1")
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("mcp", parents=[common], help="run the cleo-feedback-store MCP server")
    p.add_argument("--transport", choices=("stdio", "sse", "streamable-http"), default="stdio")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.set_defaults(func=cmd_mcp)

    p = sub.add_parser("status", parents=[common], help="runtime status without a server")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("overview", parents=[common], help="workspace overview (counts, urgent themes, brief)")
    p.set_defaults(func=cmd_overview)

    p = sub.add_parser("skills", parents=[common], help="list or show skills")
    skills_sub = p.add_subparsers(dest="skills_command", required=True, metavar="subcommand")
    sp = skills_sub.add_parser("list", parents=[common], help="list all skills (authored + learned)")
    sp.set_defaults(func=cmd_skills_list)
    sp = skills_sub.add_parser("show", parents=[common], help="show one skill's full procedure")
    sp.add_argument("name", help="kebab-case skill name")
    sp.set_defaults(func=cmd_skills_show)

    p = sub.add_parser("handoffs", parents=[common], help="list coder handoffs")
    handoffs_sub = p.add_subparsers(dest="handoffs_command", required=True, metavar="subcommand")
    hp = handoffs_sub.add_parser("list", parents=[common], help="list handoffs")
    hp.add_argument("--status", choices=("open", "in_progress", "done", "failed"), default="")
    hp.set_defaults(func=cmd_handoffs_list)

    p = sub.add_parser(
        "triage", parents=[common],
        help="LIVE: run a full agent triage (needs GOOGLE_API_KEY); streams events",
    )
    p.add_argument("--message", help=f"instruction for the operator (default: {DEFAULT_TRIAGE_MESSAGE!r})")
    p.set_defaults(func=cmd_triage)

    return parser


def main(argv: list[str] | None = None) -> None:
    # Windows consoles default to cp1252; JSON stays ASCII-safe but human
    # output may carry corpus text, so prefer UTF-8 when reconfigure exists.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError, io.UnsupportedOperation):
            pass
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
