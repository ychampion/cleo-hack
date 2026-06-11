"""Live demo of the closed fix loop (CONTRACTS §12/§13) — NOT part of pytest.

handoff -> coder -> verified green tests, end to end with the real model:

  1. ensure a checkout-themed handoff exists (creates one if the operator
     hasn't already), with evidence ids pulled from the feedback store
  2. run ONLY the coder sub-agent on it through the ADK Runner, streaming
     every tool call / response / utterance like live_smoke does
  3. verify ground truth afterwards: the handoff is "done" in the store AND
     `run_workspace_tests` reports 0 failed (deterministic, no model calls)
  4. print the final handoff + a git-style summary of workspace changes

Requires GOOGLE_API_KEY. Quota-frugal by design: a single user turn, and the
coder's instruction caps fix attempts at 3 (~5-8 model calls total).

Run: ``uv run python scripts/demo_fix_loop.py``
Reset the demo afterwards: ``git checkout -- workspace/``
Exits non-zero on any failure.
"""

from __future__ import annotations

import asyncio
import difflib
import json
import os
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))  # repo is not an installed package

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env", override=False)

# Pin the db path to an absolute location BEFORE any store import so this
# script, the coder's store-MCP subprocess, and the UI all see one database
# regardless of cwd.
_db = Path(os.environ.get("CLEO_DB_PATH", "data/cleo.db"))
os.environ["CLEO_DB_PATH"] = str(_db if _db.is_absolute() else REPO_ROOT / _db)

WORKSPACE_PREFIX = "workspace/"


def fail(step: str, message: str) -> None:
    print(f"\n[FAIL] {step}: {message}")
    sys.exit(1)


def ok(step: str, message: str) -> None:
    print(f"[ OK ] {step}: {message}")


def ensure_handoff() -> str:
    """Reuse an open checkout handoff, or create one from the corpus theme."""
    from mcp_server.handoff_tools import create_handoff, list_handoffs
    from mcp_server.server import get_store

    for h in list_handoffs(status="open")["handoffs"]:
        haystack = f"{h.get('title', '')} {h.get('problem', '')}".lower()
        if "checkout" in haystack:
            ok("handoff", f"reusing open handoff {h['id']}: {h['title']!r}")
            return h["id"]

    # Evidence straight from the feedback store (empty list if not seeded —
    # the loop still demos, just without fb_ links).
    evidence = [
        f["id"]
        for f in get_store().search_text("feedback", "checkout", limit=3)
    ]
    res = create_handoff(
        {
            "title": "Fix business-plan checkout 500s above 10 seats (v2.3 regression)",
            "problem": (
                "Since v2.3, POST /billing/checkout returns HTTP 500 for the "
                "business plan whenever seats > 10. Customers hitting it are "
                "threatening to churn. The volume-pricing tier introduced in "
                "v2.3 appears to be the trigger."
            ),
            "evidence_ids": evidence,
            "acceptance": [
                "POST /billing/checkout returns 200 for business plan with 12 seats",
                "the workspace test suite (workspace/lumen_checkout/tests) reports 0 failed",
            ],
        }
    )
    if res.get("status") != "success":
        fail("handoff", f"create_handoff errored: {res}")
    ok("handoff", f"created handoff {res['id']} ({len(evidence)} evidence ids)")
    return res["id"]


def snapshot_workspace() -> dict[str, str]:
    """Path -> content for every text file under workspace/ (pre-run baseline)."""
    from agents.cleo.coder_tools import WORKSPACE_ROOT

    snap: dict[str, str] = {}
    for p in sorted(WORKSPACE_ROOT.rglob("*")):
        rel = p.relative_to(WORKSPACE_ROOT).as_posix()
        if p.is_file() and "__pycache__" not in rel and p.suffix != ".pyc":
            try:
                snap[rel] = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue  # binary: not diffable, the coder only writes text
    return snap


def print_workspace_diff(before: dict[str, str]) -> None:
    """git-style change summary (computed in-process; no git invocation)."""
    after = snapshot_workspace()
    changed = False
    print("\n--- workspace changes ---")
    for rel in sorted(set(before) | set(after)):
        old, new = before.get(rel), after.get(rel)
        if old == new:
            continue
        changed = True
        marker = "A" if old is None else ("D" if new is None else "M")
        diff = list(
            difflib.unified_diff(
                (old or "").splitlines(),
                (new or "").splitlines(),
                fromfile=f"a/{WORKSPACE_PREFIX}{rel}",
                tofile=f"b/{WORKSPACE_PREFIX}{rel}",
                lineterm="",
            )
        )
        added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
        print(f"{marker} {WORKSPACE_PREFIX}{rel} | +{added} -{removed}")
        for line in diff[:40]:
            print(f"    {line}")
    if not changed:
        print("(no files changed)")
    print("--- end workspace changes ---")


async def run_coder(handoff_id: str) -> None:
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    from agents.cleo.sub_agents.coder import make_coder

    runner = InMemoryRunner(agent=make_coder(), app_name="cleo")
    await runner.session_service.create_session(
        app_name="cleo",
        user_id="demo",
        session_id="fixloop",
        state={"handoff_id": handoff_id},
    )
    message = types.Content(
        role="user",
        parts=[types.Part(text=f"Work handoff {handoff_id} to completion.")],
    )
    print("\n--- coder event trace ---")
    events = 0
    async for event in runner.run_async(
        user_id="demo", session_id="fixloop", new_message=message
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
    print("--- end trace ---")
    if events == 0:
        fail("coder", "runner produced no events")


def main() -> None:
    model = os.environ.get("CLEO_MODEL", "gemini-3.5-flash")
    print(f"cleo demo fix loop — model={model} repo={REPO_ROOT}")
    if not os.environ.get("GOOGLE_API_KEY", "").strip():
        fail("env", "GOOGLE_API_KEY is not set (load it via .env)")

    handoff_id = ensure_handoff()
    before = snapshot_workspace()

    try:
        asyncio.run(run_coder(handoff_id))
    except SystemExit:
        raise
    except Exception as exc:
        traceback.print_exc()
        fail("coder", f"runner raised: {exc}")

    # Ground truth, never the model's word for it.
    from agents.cleo.coder_tools import run_workspace_tests
    from mcp_server.handoff_tools import get_handoff

    got = get_handoff(handoff_id)
    if got.get("status") != "success":
        fail("verify", f"handoff vanished from the store: {got}")
    handoff = got["handoff"]
    print("\n--- final handoff ---")
    print(json.dumps(handoff, indent=2))

    print_workspace_diff(before)

    tests = run_workspace_tests()
    if tests.get("status") != "success":
        fail("verify", f"workspace test run errored: {tests.get('message', tests)}")
    ok("verify", f"workspace tests: {tests['passed']} passed, {tests['failed']} failed")

    if handoff.get("status") != "done":
        fail("verify", f"handoff finished as {handoff.get('status')!r}, expected 'done'")
    if tests["failed"] != 0:
        fail("verify", "handoff is 'done' but the workspace suite is still red")
    ok("verify", f"handoff {handoff_id} done; result: {handoff.get('result')}")
    print("\nfix loop demo passed. reset with: git checkout -- workspace/")


if __name__ == "__main__":
    main()
