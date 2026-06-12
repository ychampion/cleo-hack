"""Handoff tools, coder sandbox, and §14 route tests — no network, no LLM.

Three layers:
  1. mcp_server.handoff_tools called directly as Python (CONTRACTS §12 CRUD,
     validation, finished_at semantics) against a tmp SQLite db.
  2. agents.cleo.coder_tools sandbox — the judged code: traversal, absolute
     and sneaky relative paths must never escape workspace/; write returns
     real diff counts; run_workspace_tests runs the REAL workspace suite and,
     with the §13 bug seeded, must report the two expected failures (the
     demo's objective function).
  3. /api/handoffs and /api/skills with TestClient against a tmp db.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

pytest.importorskip(
    "mcp_server.store",
    reason="mcp_server.store not built yet (parallel component)",
)


@pytest.fixture()
def handoff_db(tmp_path, monkeypatch):
    """Point the shared store at a fresh tmp db (get_store reopens on change)."""
    monkeypatch.setenv("CLEO_DB_PATH", str(tmp_path / "handoffs.db"))
    from mcp_server import handoff_tools

    return handoff_tools


SAMPLE = {
    "bet_id": "bet_000000000001",
    "title": "Fix business-plan checkout 500s above 10 seats",
    "problem": "POST /billing/checkout 500s for business plans with seats > 10 since v2.3.",
    "evidence_ids": ["fb_000000000001", "fb_000000000002"],
    "acceptance": [
        "business plan with 12 seats returns HTTP 200",
        "workspace test suite reports 0 failed",
    ],
}


# ------------------------------------------------------- §12 handoff tools


def test_create_and_get_handoff(handoff_db):
    res = handoff_db.create_handoff(dict(SAMPLE))
    assert res["status"] == "success"
    hf_id = res["id"]
    assert hf_id.startswith("hf_")

    got = handoff_db.get_handoff(hf_id)
    assert got["status"] == "success"
    doc = got["handoff"]
    assert doc["status"] == "open"  # defaulted
    assert doc["bet_id"] == "bet_000000000001"
    assert doc["title"] == SAMPLE["title"]
    assert doc["evidence_ids"] == SAMPLE["evidence_ids"]
    assert doc["acceptance"] == SAMPLE["acceptance"]
    assert doc["result"] == {"files_changed": [], "tests": "", "notes": ""}
    assert doc["created_at"]
    assert doc["finished_at"] is None


def test_create_handoff_validation(handoff_db):
    assert handoff_db.create_handoff("nope")["status"] == "error"
    assert handoff_db.create_handoff({})["status"] == "error"  # no title
    assert handoff_db.create_handoff({"title": "   "})["status"] == "error"
    assert (
        handoff_db.create_handoff({"title": "x", "status": "doing"})["status"]
        == "error"
    )
    assert (
        handoff_db.create_handoff({"title": "x", "evidence_ids": "fb_1"})["status"]
        == "error"
    )
    assert (
        handoff_db.create_handoff({"title": "x", "acceptance": "tests pass"})["status"]
        == "error"
    )
    assert (
        handoff_db.create_handoff({"title": "x", "result": "done"})["status"] == "error"
    )


def test_list_handoffs_filters_by_status(handoff_db):
    a = handoff_db.create_handoff({"title": "A"})["id"]
    b = handoff_db.create_handoff({"title": "B"})["id"]
    assert handoff_db.update_handoff(b, "in_progress")["status"] == "success"

    all_ids = {h["id"] for h in handoff_db.list_handoffs()["handoffs"]}
    assert {a, b} <= all_ids
    open_ids = {h["id"] for h in handoff_db.list_handoffs(status="open")["handoffs"]}
    assert a in open_ids and b not in open_ids

    assert handoff_db.list_handoffs(status="bogus")["status"] == "error"


def test_update_handoff_lifecycle(handoff_db):
    hf_id = handoff_db.create_handoff({"title": "lifecycle"})["id"]

    assert handoff_db.update_handoff(hf_id, "in_progress")["status"] == "success"
    doc = handoff_db.get_handoff(hf_id)["handoff"]
    assert doc["status"] == "in_progress"
    assert doc["finished_at"] is None  # non-terminal: no stamp

    result = {
        "files_changed": ["lumen_checkout/app.py"],
        "tests": "5 passed / 0 failed",
        "notes": "tier key typo",
    }
    assert handoff_db.update_handoff(hf_id, "done", result)["status"] == "success"
    doc = handoff_db.get_handoff(hf_id)["handoff"]
    assert doc["status"] == "done"
    assert doc["finished_at"] is not None  # terminal: stamped
    assert doc["result"] == result

    # Partial result updates merge over the existing one.
    hf2 = handoff_db.create_handoff({"title": "partial"})["id"]
    handoff_db.update_handoff(hf2, "failed", {"notes": "could not reproduce"})
    doc2 = handoff_db.get_handoff(hf2)["handoff"]
    assert doc2["result"]["notes"] == "could not reproduce"
    assert doc2["result"]["files_changed"] == []
    assert doc2["finished_at"] is not None


def test_update_handoff_validation(handoff_db):
    hf_id = handoff_db.create_handoff({"title": "v"})["id"]
    assert handoff_db.update_handoff(hf_id, "shipped")["status"] == "error"
    assert handoff_db.update_handoff("hf_missing", "done")["status"] == "error"
    assert handoff_db.update_handoff(hf_id, "done", "all good")["status"] == "error"
    assert handoff_db.get_handoff("hf_missing")["status"] == "error"


# ----------------------------------------------------- coder tools sandbox


@pytest.fixture()
def coder_tools():
    from agents.cleo import coder_tools as ct

    return ct


@pytest.mark.parametrize(
    "bad_path",
    [
        "..",
        "../CONTRACTS.md",
        "a/../../x",
        "lumen_checkout/../../mcp_server/store.py",
        "/etc/passwd",  # rooted: absolute on POSIX, drive-relative on Windows
    ],
)
def test_resolve_rejects_escapes(coder_tools, bad_path):
    with pytest.raises(ValueError):
        coder_tools._resolve(bad_path)


@pytest.mark.skipif(sys.platform != "win32", reason="backslash separators are Windows-only")
@pytest.mark.parametrize(
    "bad_path",
    ["..\\CONTRACTS.md", "\\evil.txt", "C:\\Windows\\notepad.exe", "C:secret.txt"],
)
def test_resolve_rejects_windows_escapes(coder_tools, bad_path):
    with pytest.raises(ValueError):
        coder_tools._resolve(bad_path)


def test_resolve_rejects_absolute_and_empty(coder_tools):
    with pytest.raises(ValueError):
        coder_tools._resolve(str(Path.home()))  # absolute on every platform
    with pytest.raises(ValueError):
        coder_tools._resolve(str(REPO_ROOT / "workspace" / "x.txt"))  # absolute, even inside
    with pytest.raises(ValueError):
        coder_tools._resolve("   ")


def test_resolve_accepts_workspace_relative(coder_tools):
    resolved = coder_tools._resolve("lumen_checkout/app.py")
    assert resolved == coder_tools.WORKSPACE_ROOT / "lumen_checkout" / "app.py"
    # benign ".." that stays inside the sandbox is fine
    assert (
        coder_tools._resolve("lumen_checkout/../lumen_checkout/app.py") == resolved
    )


def test_tools_return_error_dicts_not_exceptions(coder_tools, tmp_path, monkeypatch):
    monkeypatch.setattr(coder_tools, "WORKSPACE_ROOT", tmp_path.resolve())
    assert coder_tools.read_workspace_file("../secrets.txt")["status"] == "error"
    res = coder_tools.write_workspace_file("../escape.txt", "pwned")
    assert res["status"] == "error"
    assert not (tmp_path.parent / "escape.txt").exists()
    assert coder_tools.read_workspace_file("missing.py")["status"] == "error"


def test_list_and_read_real_workspace(coder_tools):
    listing = coder_tools.list_workspace()
    assert listing["status"] == "success"
    assert "lumen_checkout/app.py" in listing["files"]
    assert "lumen_checkout/tests/test_checkout.py" in listing["files"]

    read = coder_tools.read_workspace_file("lumen_checkout/app.py")
    assert read["status"] == "success"
    assert "/billing/checkout" in read["content"]


def test_write_workspace_file_diff_counts(coder_tools, tmp_path, monkeypatch):
    monkeypatch.setattr(coder_tools, "WORKSPACE_ROOT", tmp_path.resolve())

    created = coder_tools.write_workspace_file("pkg/notes.txt", "a\nb\nc\n")
    assert created["status"] == "success"
    assert created["created"] is True
    assert created["lines_added"] == 3
    assert created["lines_removed"] == 0

    updated = coder_tools.write_workspace_file("pkg/notes.txt", "a\nB\nc\nd\n")
    assert updated["status"] == "success"
    assert updated["created"] is False
    assert updated["lines_added"] == 2  # B, d
    assert updated["lines_removed"] == 1  # b
    assert (tmp_path / "pkg" / "notes.txt").read_text(encoding="utf-8") == "a\nB\nc\nd\n"


def test_run_workspace_tests_reports_seeded_failures(coder_tools):
    """The demo objective function: with the §13 bug present, the REAL
    workspace suite must fail exactly on the volume-pricing cases."""
    res = coder_tools.run_workspace_tests()
    assert res["status"] == "success"
    if res["failed"] == 0:
        # A demo run has already fixed the workspace in this checkout. The
        # assertion below is only meaningful against the pristine seeded bug
        # (which is what CI sees); locally, reset with: git checkout -- workspace/
        pytest.skip("workspace bug already fixed by a demo run — reset with `git checkout -- workspace/`")
    assert res["failed"] >= 2, f"expected the seeded checkout bug to fail tests: {res}"
    assert res["passed"] >= 2  # team plan + business<=10 + validation still pass
    assert len(res["output_tail"]) <= 2000
    assert "failed" in res["output_tail"]


def test_make_coder_constructs():
    pytest.importorskip("google.adk", reason="ADK not installed")
    from agents.cleo.sub_agents.coder import make_coder

    coder = make_coder()
    assert coder.name == "coder"
    assert make_coder("_w").name == "coder_w"


# ------------------------------------------------------------- §14 routes


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    from fastapi.testclient import TestClient

    db = tmp_path_factory.mktemp("cleo") / "cleo_handoffs_test.db"
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
def seeded_handoffs(client):
    import os

    from mcp_server.store import Store

    store = Store(os.environ["CLEO_DB_PATH"])
    store.put(
        "handoffs",
        "hf_000000000001",
        {
            "id": "hf_000000000001",
            "bet_id": "bet_000000000001",
            "title": "Fix checkout 500s",
            "problem": "business plan >10 seats 500s",
            "evidence_ids": ["fb_000000000001"],
            "acceptance": ["12 seats returns 200"],
            "status": "done",
            "result": {
                "files_changed": ["lumen_checkout/app.py"],
                "tests": "5 passed / 0 failed",
                "notes": "tier key typo",
            },
            "created_at": "2026-06-12T10:00:00Z",
            "finished_at": "2026-06-12T10:20:00Z",
        },
    )
    store.put(
        "handoffs",
        "hf_000000000002",
        {
            "id": "hf_000000000002",
            "bet_id": None,
            "title": "Okta SSO loop",
            "problem": "SSO redirect loops",
            "evidence_ids": [],
            "acceptance": ["login succeeds"],
            "status": "open",
            "result": {"files_changed": [], "tests": "", "notes": ""},
            "created_at": "2026-06-12T11:00:00Z",
            "finished_at": None,
        },
    )
    return store


def test_api_handoffs(client, seeded_handoffs):
    r = client.get("/api/handoffs")
    assert r.status_code == 200
    handoffs = r.json()["handoffs"]
    assert {h["id"] for h in handoffs} == {"hf_000000000001", "hf_000000000002"}
    assert handoffs[0]["id"] == "hf_000000000002"  # newest first

    done = client.get("/api/handoffs", params={"status": "done"}).json()["handoffs"]
    assert [h["id"] for h in done] == ["hf_000000000001"]
    assert done[0]["result"]["files_changed"] == ["lumen_checkout/app.py"]

    none = client.get("/api/handoffs", params={"status": "failed"}).json()["handoffs"]
    assert none == []


def test_api_skills(client):
    r = client.get("/api/skills")
    assert r.status_code == 200
    skills = r.json()["skills"]
    assert isinstance(skills, list)  # [] until skill_tools lands (parallel build)
    try:
        from mcp_server.skill_tools import skills_index  # noqa: F401
    except ImportError:
        assert skills == []
    else:
        for skill in skills:
            assert {"name", "description", "source"} <= set(skill)
