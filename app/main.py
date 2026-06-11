"""Cleo server: ADK runner app + custom /api routes + built SPA (CONTRACTS §5).

``get_fast_api_app`` wraps the whole ADK runtime — agent discovery from
``agents/``, sessions, ``POST /run_sse`` event streaming — so the UI talks to
ONE origin for both the product API and live agent runs. ``web=False``
selects ADK's production-safe ApiServer surface (no dev UI endpoints).

Mount order is load-bearing: API routers must be registered before the SPA
static mount at "/" because Starlette matches mounts greedily — a "/" mount
registered first would shadow every /api route.

Run: ``uv run uvicorn app.main:app --port 8080``.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]

# Env first: get_fast_api_app and agent construction read CLEO_MODEL /
# GITHUB_TOKEN / CLEO_DB_PATH at import time.
load_dotenv(REPO_ROOT / ".env", override=False)

# The SQLite file's parent must exist before any component opens it.
_db = Path(os.environ.get("CLEO_DB_PATH", "data/cleo.db"))
if not _db.is_absolute():
    _db = REPO_ROOT / _db
_db.parent.mkdir(parents=True, exist_ok=True)

from fastapi.staticfiles import StaticFiles  # noqa: E402
from google.adk.cli.fast_api import get_fast_api_app  # noqa: E402

from .api import router as api_router  # noqa: E402

app = get_fast_api_app(
    # Absolute path so uvicorn/pytest work from any cwd, not just repo root.
    agents_dir=str(REPO_ROOT / "agents"),
    # Empty -> in-memory sessions: a demo run's session is disposable; all
    # durable state lives in the SQLite store the agent writes through MCP.
    session_service_uri="",
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    web=False,
)

app.include_router(api_router)

# Serve the built SPA at "/" only when it exists (web/ is built separately);
# html=True gives index.html fallback for client-side routes.
_dist = REPO_ROOT / "web" / "dist"
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="spa")
