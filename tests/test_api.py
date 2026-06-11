"""FastAPI route tests against CONTRACTS §5 — no network, no LLM.

The app is imported once per module with CLEO_DB_PATH pointed at a temp file
and GITHUB_TOKEN forced empty (so no GitHub toolset is composed). Env is set
BEFORE importing app.main because agents/cleo loads .env with override=False:
pre-set (even empty) vars win over the developer's .env.

POST /api/agent/run exercises the real ADK session route in-process (session
creation never invokes the model), so the ADK wiring is covered too.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
# Repo is not an installed package (tool.uv package=false): make repo-root
# imports (app, agents, mcp_server) work under pytest, same as test_store.py.
sys.path.insert(0, str(REPO_ROOT))

pytest.importorskip(
    "mcp_server.store",
    reason="mcp_server.store not built yet (parallel component)",
)


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    from fastapi.testclient import TestClient

    db = tmp_path_factory.mktemp("cleo") / "cleo_test.db"
    mp = pytest.MonkeyPatch()
    mp.setenv("CLEO_DB_PATH", str(db))
    mp.setenv("GITHUB_TOKEN", "")  # empty (not deleted): wins over .env
    mp.setenv("GITHUB_DEMO_REPO", "")

    # Fresh import so module-level env reads (agents dir, dotenv) see ours.
    for name in [m for m in sys.modules if m.startswith(("app", "agents.cleo"))]:
        del sys.modules[name]
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
    mp.undo()


@pytest.fixture(scope="module")
def seeded(client):
    """Deterministic store contents shared by all tests in this module."""
    from mcp_server.store import Store

    import os

    store = Store(os.environ["CLEO_DB_PATH"])
    feedback = [
        {
            "id": "fb_000000000001",
            "source": "github",
            "external_id": "1",
            "author": "alice",
            "text": "Checkout returns 500 after v2.3, we will churn",
            "url": "https://github.com/lumen/app/issues/1",
            "created_at": "2026-06-10T10:00:00Z",
            "ingested_at": "2026-06-10T10:05:00Z",
            "urgency": 3,
            "sentiment": "neg",
            "theme_id": "th_000000000001",
            "metadata": {},
        },
        {
            "id": "fb_000000000002",
            "source": "call",
            "external_id": "call-1#1",
            "author": "bob",
            "text": "Would love CSV export of dashboards",
            "url": None,
            "created_at": "2026-06-11T10:00:00Z",
            "ingested_at": "2026-06-11T10:05:00Z",
            "urgency": None,
            "sentiment": None,
            "theme_id": None,
            "metadata": {},
        },
        {
            "id": "fb_000000000003",
            "source": "doc",
            "external_id": "nps#1",
            "author": "carol",
            "text": "Dashboard loads slowly on big workspaces",
            "url": None,
            "created_at": "2026-06-12T10:00:00Z",
            "ingested_at": "2026-06-12T10:05:00Z",
            "urgency": 1,
            "sentiment": "neu",
            "theme_id": "th_000000000002",
            "metadata": {},
        },
    ]
    for f in feedback:
        store.put("feedback", f["id"], f)

    themes = [
        {
            "id": "th_000000000001",
            "title": "Checkout 500s after v2.3",
            "summary": "Multiple churn threats tied to checkout failures.",
            "urgency": 3,
            "trend": "new",
            "feedback_ids": ["fb_000000000001"],
            "first_seen": "2026-06-10T10:00:00Z",
            "last_seen": "2026-06-10T10:00:00Z",
        },
        {
            "id": "th_000000000002",
            "title": "Dashboard slowness",
            "summary": "Performance complaints on large workspaces.",
            "urgency": 1,
            "trend": "steady",
            "feedback_ids": ["fb_000000000003"],
            "first_seen": "2026-06-12T10:00:00Z",
            "last_seen": "2026-06-12T10:00:00Z",
        },
    ]
    for t in themes:
        store.put("themes", t["id"], t)

    store.put(
        "bets",
        "bet_000000000001",
        {
            "id": "bet_000000000001",
            "title": "Fix checkout 500s",
            "problem": "Checkout fails post v2.3",
            "proposal": "Roll back payment middleware",
            "impact": 5,
            "effort": 2,
            "confidence": 0.9,
            "urgency": 3,
            "theme_ids": ["th_000000000001"],
            "evidence_ids": ["fb_000000000001"],
            "status": "proposed",
            "created_at": "2026-06-12T11:00:00Z",
        },
    )
    store.put(
        "actions",
        "act_000000000001",
        {
            "id": "act_000000000001",
            "type": "github_issue",
            "status": "executed",
            "target": "lumen/app",
            "payload": {"title": "[Cleo] Checkout 500s"},
            "rationale": "urgent churn risk under directive",
            "evidence_ids": ["fb_000000000001"],
            "created_at": "2026-06-12T11:10:00Z",
            "executed_at": "2026-06-12T11:11:00Z",
            "result": {"number": 42},
        },
    )
    store.put(
        "actions",
        "act_000000000002",
        {
            "id": "act_000000000002",
            "type": "github_comment",
            "status": "skipped",
            "target": "other/repo",
            "payload": {},
            "rationale": "blocked by action_guard: target not authorized",
            "evidence_ids": [],
            "created_at": "2026-06-12T11:20:00Z",
            "executed_at": None,
            "result": {},
        },
    )
    store.put(
        "briefs",
        "br_000000000001",
        {
            "id": "br_000000000001",
            "week": "2026-W24",
            "markdown": "# Product Brief",
            "theme_ids": ["th_000000000001"],
            "created_at": "2026-06-12T12:00:00Z",
        },
    )
    store.put(
        "directives",
        "dir_000000000001",
        {
            "id": "dir_000000000001",
            "text": "Triage all new feedback and escalate urgent churn risks.",
            "active": True,
            "created_at": "2026-06-09T08:00:00Z",
        },
    )
    return store


def test_runtime_status(client, seeded):
    r = client.get("/api/runtime/status")
    assert r.status_code == 200
    body = r.json()
    assert body["model"]  # CLEO_MODEL or the gemini-3.5-flash default
    assert body["github_token_present"] is False
    assert body["db_path"].endswith("cleo_test.db")
    assert body["feedback_count"] == 3
    assert body["store_ready"] is True
    assert isinstance(body["google_api_key_present"], bool)


def test_overview(client, seeded):
    r = client.get("/api/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["counts"] == {
        "feedback": 3,
        "untriaged": 1,
        "themes": 2,
        "bets": 1,
        "actions_executed": 1,
    }
    assert [t["id"] for t in body["urgent"]] == ["th_000000000001"]
    assert body["latest_brief"]["id"] == "br_000000000001"
    assert len(body["recent_actions"]) == 2
    assert body["top_themes"][0]["id"] == "th_000000000001"


def test_feedback_filters(client, seeded):
    assert len(client.get("/api/feedback").json()["items"]) == 3

    items = client.get("/api/feedback", params={"source": "call"}).json()["items"]
    assert [f["id"] for f in items] == ["fb_000000000002"]

    items = client.get(
        "/api/feedback", params={"theme_id": "th_000000000002"}
    ).json()["items"]
    assert [f["id"] for f in items] == ["fb_000000000003"]

    items = client.get("/api/feedback", params={"urgency": 3}).json()["items"]
    assert [f["id"] for f in items] == ["fb_000000000001"]

    items = client.get("/api/feedback", params={"limit": 1}).json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == "fb_000000000003"  # newest first


def test_collection_routes(client, seeded):
    themes = client.get("/api/themes").json()["themes"]
    assert {t["id"] for t in themes} == {"th_000000000001", "th_000000000002"}

    bets = client.get("/api/bets").json()["bets"]
    assert bets[0]["id"] == "bet_000000000001"

    actions = client.get("/api/actions", params={"status": "executed"}).json()["actions"]
    assert [a["id"] for a in actions] == ["act_000000000001"]
    assert len(client.get("/api/actions").json()["actions"]) == 2

    brief = client.get("/api/briefs/latest").json()["brief"]
    assert brief["id"] == "br_000000000001"


def test_directives_flow(client, seeded):
    r = client.post("/api/directives", json={"text": "Keep the weekly brief current."})
    assert r.status_code == 200
    created = r.json()
    assert created["id"].startswith("dir_")
    assert created["active"] is True

    ids = {d["id"] for d in client.get("/api/directives").json()["directives"]}
    assert {created["id"], "dir_000000000001"} <= ids

    r = client.patch(f"/api/directives/{created['id']}", json={"active": False})
    assert r.status_code == 200
    assert r.json()["active"] is False

    by_id = {
        d["id"]: d for d in client.get("/api/directives").json()["directives"]
    }
    assert by_id[created["id"]]["active"] is False  # listed, but inactive

    assert client.post("/api/directives", json={"text": "  "}).status_code == 422
    assert (
        client.patch("/api/directives/dir_nope", json={"active": True}).status_code
        == 404
    )


def test_agent_run_creates_session_and_run_row(client, seeded):
    r = client.post("/api/agent/run", json={"message": "triage now"})
    assert r.status_code == 200
    run_id = r.json()["run_id"]
    assert run_id.startswith("run_")

    run = client.get(f"/api/runs/{run_id}").json()
    assert run["status"] == "running"
    assert run["trigger"] == "manual"
    assert run["summary"] == "triage now"

    assert run_id in {x["id"] for x in client.get("/api/runs").json()["runs"]}

    # The ADK session (cleo/operator/ui) must now exist on ADK's own routes.
    s = client.get("/apps/cleo/users/operator/sessions/ui")
    assert s.status_code == 200

    # Idempotent: a second run reuses the existing session.
    r2 = client.post("/api/agent/run", json={})
    assert r2.status_code == 200
    assert r2.json()["run_id"] != run_id

    assert client.get("/api/runs/run_missing").status_code == 404
