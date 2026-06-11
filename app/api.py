"""Custom /api routes for the Cleo UI (CONTRACTS §5).

These routes read the SQLite store DIRECTLY via ``mcp_server.store.Store``
rather than through MCP: MCP is the *agent's* boundary to the world; the UI's
read path is plain server code and a round-trip through a tool protocol would
add latency and failure modes for zero gain. Writes that matter (actions,
themes, bets) still only happen through the agent + its guarded tools — the
UI can only create/toggle directives and open runs.

Response-shape conventions: ``GET /api/feedback`` returns ``{items}`` (per §5
verbatim); the other list routes mirror the §2 store-tool envelopes
(``{themes}``, ``{bets}``, ``{actions}``, ``{brief}``, ``{directives}``,
``{runs}``) so the web client sees one consistent vocabulary.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[1]

# The session triple the UI uses for everything (CONTRACTS §5): the SPA calls
# ADK's own POST /run_sse with these same values to stream events.
ADK_APP_NAME = "cleo"
ADK_USER_ID = "operator"
ADK_SESSION_ID = "ui"

router = APIRouter(prefix="/api")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_path() -> Path:
    raw = Path(os.environ.get("CLEO_DB_PATH", "data/cleo.db"))
    return raw if raw.is_absolute() else REPO_ROOT / raw


def _store():
    """Open the store fresh per request: cheap (SQLite handle) and always
    honors a changed CLEO_DB_PATH (tests monkeypatch it)."""
    try:
        from mcp_server.store import Store  # noqa: PLC0415
    except ImportError as exc:  # mcp_server is built by a parallel component
        raise HTTPException(
            status_code=503, detail=f"feedback store not available: {exc}"
        ) from exc
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return Store(str(path))


def _rows(store: Any, collection: str) -> list[dict]:
    """Normalize Store.list() rows to payload dicts and sort newest-first.

    Filtering happens in Python, not via Store.list(**filters): the §0 store
    contract doesn't pin filter semantics, collections are demo-sized, and
    this keeps us decoupled from the store's internals.
    """
    out: list[dict] = []
    for row in store.list(collection) or []:
        if isinstance(row, dict) and "payload" in row and "id" not in row:
            payload = row["payload"]
            row = json.loads(payload) if isinstance(payload, str) else payload
        if isinstance(row, str):
            row = json.loads(row)
        if isinstance(row, dict):
            out.append(row)
    out.sort(key=lambda r: str(r.get("created_at") or r.get("started_at") or ""), reverse=True)
    return out


# ---------------------------------------------------------------- overview


@router.get("/overview")
def overview() -> dict:
    store = _store()
    feedback = _rows(store, "feedback")
    themes = _rows(store, "themes")
    bets = _rows(store, "bets")
    actions = _rows(store, "actions")
    briefs = _rows(store, "briefs")

    # "urgent" = themes at urgency >= 2 (CONTRACTS §1 rubric: 2 broken
    # workflow, 3 churn/outage) — the same threshold the actor escalates on.
    urgent = [t for t in themes if (t.get("urgency") or 0) >= 2]
    top_themes = sorted(
        themes,
        key=lambda t: ((t.get("urgency") or 0), len(t.get("feedback_ids") or [])),
        reverse=True,
    )[:5]
    return {
        "counts": {
            "feedback": len(feedback),
            "untriaged": sum(1 for f in feedback if f.get("theme_id") is None),
            "themes": len(themes),
            "bets": len(bets),
            "actions_executed": sum(1 for a in actions if a.get("status") == "executed"),
        },
        "urgent": urgent,
        "latest_brief": briefs[0] if briefs else None,
        "recent_actions": actions[:5],
        "top_themes": top_themes,
    }


# ---------------------------------------------------------------- feedback


@router.get("/feedback")
def list_feedback(
    source: str = "", theme_id: str = "", urgency: int | None = None, limit: int = 50
) -> dict:
    items = _rows(_store(), "feedback")
    if source:
        items = [f for f in items if f.get("source") == source]
    if theme_id:
        items = [f for f in items if f.get("theme_id") == theme_id]
    if urgency is not None:
        items = [f for f in items if f.get("urgency") == urgency]
    return {"items": items[: max(1, min(limit, 500))]}


# ------------------------------------------------- themes / bets / actions


@router.get("/themes")
def list_themes() -> dict:
    return {"themes": _rows(_store(), "themes")}


@router.get("/bets")
def list_bets() -> dict:
    return {"bets": _rows(_store(), "bets")}


@router.get("/actions")
def list_actions(status: str = "") -> dict:
    actions = _rows(_store(), "actions")
    if status:
        actions = [a for a in actions if a.get("status") == status]
    return {"actions": actions}


@router.get("/briefs/latest")
def latest_brief() -> dict:
    briefs = _rows(_store(), "briefs")
    return {"brief": briefs[0] if briefs else None}


# -------------------------------------------------------------- directives


class DirectiveIn(BaseModel):
    text: str


class DirectivePatch(BaseModel):
    active: bool


@router.get("/directives")
def list_directives() -> dict:
    # Returns ALL directives (with their active flags), unlike the store's
    # get_directives MCP tool (active-only): the UI must show inactive ones
    # so they can be re-enabled.
    return {"directives": _rows(_store(), "directives")}


@router.post("/directives")
def create_directive(body: DirectiveIn) -> dict:
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="directive text is empty")
    store = _store()
    dir_id = f"dir_{uuid.uuid4().hex[:12]}"
    doc = {"id": dir_id, "text": text, "active": True, "created_at": _now()}
    store.put("directives", dir_id, doc)
    return doc


@router.patch("/directives/{dir_id}")
def patch_directive(dir_id: str, body: DirectivePatch) -> dict:
    store = _store()
    doc = store.get("directives", dir_id)
    if isinstance(doc, str):
        doc = json.loads(doc)
    if not isinstance(doc, dict):
        raise HTTPException(status_code=404, detail="directive not found")
    doc["active"] = body.active
    store.put("directives", dir_id, doc)
    return doc


# -------------------------------------------------------------- agent runs


class AgentRunIn(BaseModel):
    message: str | None = None


@router.post("/agent/run")
async def agent_run(request: Request, body: AgentRunIn | None = None) -> dict:
    """Open a run: ensure the ADK session exists, create the `runs` row.

    The actual agent execution streams through ADK's own POST /run_sse — the
    UI calls it directly with the same (app, user, session) triple, and the
    pipeline's run_starter callback adopts the "running" row created here.

    The session is ensured by calling the ADK-generated session routes
    *in-process* via an ASGI transport: get_fast_api_app() does not expose its
    session service object, and dispatching through the app keeps us on the
    supported surface instead of reaching into ADK internals.
    """
    transport = httpx.ASGITransport(app=request.app)
    base = f"/apps/{ADK_APP_NAME}/users/{ADK_USER_ID}/sessions/{ADK_SESSION_ID}"
    async with httpx.AsyncClient(
        transport=transport, base_url="http://cleo.internal"
    ) as client:
        resp = await client.get(base)
        if resp.status_code == 404:
            resp = await client.post(base, json={})
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"could not ensure ADK session: {resp.status_code} {resp.text[:300]}",
            )

    store = _store()
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    store.put(
        "runs",
        run_id,
        {
            "id": run_id,
            "trigger": "manual",
            "started_at": _now(),
            "finished_at": None,
            "status": "running",
            "summary": (body.message if body and body.message else ""),
            "counts": {"ingested": 0, "themes": 0, "bets": 0, "actions": 0},
        },
    )
    return {"run_id": run_id}


@router.get("/runs")
def list_runs() -> dict:
    return {"runs": _rows(_store(), "runs")}


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    doc = _store().get("runs", run_id)
    if isinstance(doc, str):
        doc = json.loads(doc)
    if not isinstance(doc, dict):
        raise HTTPException(status_code=404, detail="run not found")
    return doc


# ----------------------------------------------------------------- runtime


@router.get("/runtime/status")
def runtime_status() -> dict:
    try:
        feedback_count = len(_rows(_store(), "feedback"))
        store_ready = True
    except HTTPException:
        feedback_count = 0
        store_ready = False
    return {
        "model": os.environ.get("CLEO_MODEL", "gemini-3.5-flash"),
        "google_api_key_present": bool(os.environ.get("GOOGLE_API_KEY", "").strip()),
        "github_token_present": bool(os.environ.get("GITHUB_TOKEN", "").strip()),
        "db_path": str(_db_path()),
        "feedback_count": feedback_count,
        # additive (not in §5): lets the UI distinguish "no feedback yet"
        # from "store module missing" while components land in parallel.
        "store_ready": store_ready,
    }
