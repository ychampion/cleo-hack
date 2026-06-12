"""Live smoke test (CONTRACTS §9) — requires real keys, NOT part of pytest.

Verifies the four layers that unit tests cannot (they are no-network/no-LLM):

  1. model     — direct google-genai ping with CLEO_MODEL (GOOGLE_API_KEY)
  2. store MCP — boots ``python -m mcp_server.server`` as a subprocess and
                 lists its tools over a real stdio MCP client session
  3. github    — (only if GITHUB_TOKEN) connects to the hosted GitHub MCP per
                 CONTRACTS §3 and lists issues on GITHUB_DEMO_REPO
  4. triage    — one full pipeline run through the ADK Runner with an
                 event-by-event trace (tool calls, tool responses, text)

Run: ``uv run python scripts/live_smoke.py``
Exits non-zero on the first failure with a clear message.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))  # repo is not an installed package

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env", override=False)

MODEL = os.environ.get("CLEO_MODEL", "gemini-3.5-flash")

# CONTRACTS §2 tool names the store server must expose.
EXPECTED_STORE_TOOLS = {
    "ingest_feedback",
    "list_feedback",
    "search_feedback",
    "tag_feedback",
    "save_themes",
    "list_themes",
    "save_bets",
    "list_bets",
    "record_action",
    "complete_action",
    "list_actions",
    "write_brief",
    "get_latest_brief",
    "get_directives",
    "start_run",
    "finish_run",
}


def fail(step: str, message: str) -> None:
    print(f"\n[FAIL] {step}: {message}")
    sys.exit(1)


def ok(step: str, message: str) -> None:
    print(f"[ OK ] {step}: {message}")


# ------------------------------------------------------------------ step 1


def step_model_ping() -> None:
    vertex_mode = (
        os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").strip().upper() == "TRUE"
        and os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
    )
    if not os.environ.get("GOOGLE_API_KEY", "").strip() and not vertex_mode:
        fail("model", "set GOOGLE_API_KEY, or GOOGLE_GENAI_USE_VERTEXAI=TRUE + GOOGLE_CLOUD_PROJECT (ADC), via .env")
    try:
        from google import genai

        client = genai.Client()
        resp = client.models.generate_content(
            model=MODEL, contents="Reply with exactly: pong"
        )
        text = (resp.text or "").strip()
    except Exception as exc:
        fail("model", f"generate_content with {MODEL!r} raised: {exc}")
    if not text:
        fail("model", f"{MODEL!r} returned an empty response")
    ok("model", f"{MODEL} responded: {text[:60]!r}")


# ------------------------------------------------------------------ step 2


async def step_store_mcp() -> None:
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_server.server"],
            cwd=str(REPO_ROOT),
            env={**os.environ},
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listing = await session.list_tools()
                names = {t.name for t in listing.tools}
    except Exception as exc:
        traceback.print_exc()
        fail("store-mcp", f"could not boot/list cleo-feedback-store: {exc}")
    missing = EXPECTED_STORE_TOOLS - names
    if missing:
        fail("store-mcp", f"server is missing contract tools: {sorted(missing)}")
    ok("store-mcp", f"stdio server up, {len(names)} tools, all §2 names present")


# ------------------------------------------------------------------ step 3


async def step_github_mcp() -> None:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print("[SKIP] github: GITHUB_TOKEN not set")
        return
    repo = os.environ.get("GITHUB_DEMO_REPO", "").strip()
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        from agents.cleo.toolsets import GITHUB_HOSTED_MCP_URL

        async with streamablehttp_client(
            GITHUB_HOSTED_MCP_URL, headers={"Authorization": f"Bearer {token}"}
        ) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listing = await session.list_tools()
                names = {t.name for t in listing.tools}
                if "list_issues" not in names:
                    fail("github", f"hosted server lacks list_issues ({len(names)} tools)")
                if "/" in repo:
                    owner, name = repo.split("/", 1)
                    result = await session.call_tool(
                        "list_issues", {"owner": owner, "repo": name, "perPage": 5}
                    )
                    if result.isError:
                        fail("github", f"list_issues on {repo} errored: {result.content}")
                    ok("github", f"hosted MCP connected; list_issues({repo}) succeeded")
                else:
                    ok("github", "hosted MCP connected (no GITHUB_DEMO_REPO; skipped list_issues)")
    except SystemExit:
        raise
    except Exception as exc:
        traceback.print_exc()
        fail("github", f"hosted GitHub MCP failed: {exc} "
             "(try GITHUB_MCP_STDIO=1 for the npx fallback)")


# ------------------------------------------------------------------ step 4


async def step_triage_run() -> None:
    try:
        from google.adk.runners import InMemoryRunner
        from google.genai import types

        from agents.cleo.agent import root_agent

        runner = InMemoryRunner(agent=root_agent, app_name="cleo")
        await runner.session_service.create_session(
            app_name="cleo", user_id="smoke", session_id="smoke"
        )
        message = types.Content(
            role="user",
            parts=[types.Part(text="Run a full triage of all feedback sources now.")],
        )
        print("\n--- triage run event trace ---")
        events = 0
        async for event in runner.run_async(
            user_id="smoke", session_id="smoke", new_message=message
        ):
            events += 1
            for part in event.content.parts if event.content else []:
                if part.function_call:
                    args = json.dumps(part.function_call.args or {})[:160]
                    print(f"[{event.author}] -> {part.function_call.name}({args})")
                elif part.function_response:
                    resp = str(part.function_response.response)[:160]
                    print(f"[{event.author}] <- {part.function_response.name}: {resp}")
                elif part.text and part.text.strip():
                    print(f"[{event.author}] {part.text.strip()[:240]}")
        print("--- end trace ---\n")
        if events == 0:
            fail("triage", "runner produced no events")
    except SystemExit:
        raise
    except Exception as exc:
        traceback.print_exc()
        fail("triage", f"pipeline run raised: {exc}")

    # Ground truth: what actually landed in the store.
    from mcp_server.store import Store

    db = Path(os.environ.get("CLEO_DB_PATH", "data/cleo.db"))
    store = Store(str(db if db.is_absolute() else REPO_ROOT / db))
    counts = {
        c: len(store.list(c))
        for c in ("feedback", "themes", "bets", "actions", "briefs", "runs")
    }
    ok("triage", f"run completed ({events} events); store now has {counts}")
    if counts["themes"] == 0 or counts["bets"] == 0:
        fail("triage", "run finished but produced no themes/bets — inspect the trace above")


def main() -> None:
    print(f"cleo live smoke — model={MODEL} repo={REPO_ROOT}")
    step_model_ping()
    asyncio.run(step_store_mcp())
    asyncio.run(step_github_mcp())
    asyncio.run(step_triage_run())
    print("\nall live smoke steps passed.")


if __name__ == "__main__":
    main()
