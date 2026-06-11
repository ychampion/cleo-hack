"""End-to-end tests for the `cleo` CLI (cli/main.py) — NO network, NO LLM.

Every test shells out exactly like a user or agent would
(``sys.executable -m cli.main …``), asserting on exit codes, parsed
``--json`` stdout, and the JSON error object the CLI prints to stderr on
failure. Each test gets an isolated SQLite db via ``CLEO_DB_PATH`` (absolute,
so the CLI's repo-root anchoring leaves it untouched) and, where relevant, an
isolated skills root via ``CLEO_SKILLS_DIR``.

``cleo init`` resolves its target directory from ``--dir`` when given, else
the process cwd — tests cover both (cwd=tmp_path and an explicit --dir).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_cli(
    *argv: str,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run `python -m cli.main <argv>` with the parent env + overrides."""
    full_env = {
        **os.environ,
        # Belt-and-braces: works whether or not the package is installed.
        "PYTHONPATH": str(REPO_ROOT) + os.pathsep + os.environ.get("PYTHONPATH", ""),
        **(env or {}),
    }
    return subprocess.run(
        [sys.executable, "-m", "cli.main", *argv],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(cwd or REPO_ROOT),
        env=full_env,
        timeout=120,
    )


def db_env(tmp_path: Path) -> dict[str, str]:
    return {"CLEO_DB_PATH": str(tmp_path / "cleo.db")}


# -- help / version -------------------------------------------------------------


def test_help_exits_zero():
    proc = run_cli("--help")
    assert proc.returncode == 0
    assert "usage: cleo" in proc.stdout
    for command in ("init", "serve", "mcp", "status", "overview", "skills", "handoffs", "triage"):
        assert command in proc.stdout


def test_version_exits_zero():
    proc = run_cli("--version")
    assert proc.returncode == 0
    assert proc.stdout.startswith("cleo ")


# -- status / overview ------------------------------------------------------------


def test_status_json_fresh_db(tmp_path):
    proc = run_cli("status", "--json", env=db_env(tmp_path))
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "success"
    assert payload["model"]  # env-driven; non-empty string
    assert isinstance(payload["google_api_key_present"], bool)
    assert isinstance(payload["github_token_present"], bool)
    assert payload["db_path"] == str(tmp_path / "cleo.db")
    assert payload["feedback_count"] == 0
    assert isinstance(payload["skills_count"], int)
    assert payload["store_ready"] is True


def test_status_counts_feedback(tmp_path):
    # Pre-populate the isolated db directly through the store, then assert the
    # CLI reads the same file (proves CLEO_DB_PATH plumbing end to end).
    sys.path.insert(0, str(REPO_ROOT))
    from mcp_server.store import Store

    store = Store(tmp_path / "cleo.db")
    store.put("feedback", "fb_000000000001", {"id": "fb_000000000001", "text": "hi"})
    store.close()

    proc = run_cli("status", "--json", env=db_env(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["feedback_count"] == 1


def test_overview_json_fresh_db(tmp_path):
    proc = run_cli("overview", "--json", env=db_env(tmp_path))
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "success"
    assert payload["counts"]["feedback"] == 0
    assert payload["urgent"] == []
    assert payload["latest_brief_week"] is None


# -- skills -----------------------------------------------------------------------


def make_skill(root: Path, name: str, description: str = "Test skill.") -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f'---\nname: {name}\ndescription: "{description}"\n---\n\nStep 1: test.\n',
        encoding="utf-8",
    )


def test_skills_list_json(tmp_path):
    skills_root = tmp_path / "skills"
    make_skill(skills_root, "demo-skill", "A deterministic test skill.")
    proc = run_cli(
        "skills", "list", "--json",
        env={**db_env(tmp_path), "CLEO_SKILLS_DIR": str(skills_root)},
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "success"
    assert payload["skills"] == [
        {
            "name": "demo-skill",
            "description": "A deterministic test skill.",
            "source": "authored",
        }
    ]


def test_skills_show_json(tmp_path):
    skills_root = tmp_path / "skills"
    make_skill(skills_root, "demo-skill")
    proc = run_cli(
        "skills", "show", "demo-skill", "--json",
        env={**db_env(tmp_path), "CLEO_SKILLS_DIR": str(skills_root)},
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "success"
    assert payload["name"] == "demo-skill"
    assert "Step 1" in payload["body"]


def test_skills_show_missing_is_json_error(tmp_path):
    proc = run_cli(
        "skills", "show", "no-such-skill", "--json",
        env={**db_env(tmp_path), "CLEO_SKILLS_DIR": str(tmp_path / "skills")},
    )
    assert proc.returncode != 0
    error = json.loads(proc.stderr)
    assert error["status"] == "error"
    assert "no-such-skill" in error["message"]


# -- handoffs ---------------------------------------------------------------------


def test_handoffs_list_json_empty(tmp_path):
    proc = run_cli("handoffs", "list", "--json", env=db_env(tmp_path))
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "success"
    assert payload["handoffs"] == []


def test_handoffs_list_status_filter(tmp_path):
    sys.path.insert(0, str(REPO_ROOT))
    from mcp_server.store import Store

    store = Store(tmp_path / "cleo.db")
    store.put(
        "handoffs",
        "hf_000000000001",
        {"id": "hf_000000000001", "title": "Fix checkout", "status": "open", "result": {}},
    )
    store.close()

    proc = run_cli("handoffs", "list", "--status", "open", "--json", env=db_env(tmp_path))
    assert proc.returncode == 0, proc.stderr
    handoffs = json.loads(proc.stdout)["handoffs"]
    assert [h["id"] for h in handoffs] == ["hf_000000000001"]

    proc = run_cli("handoffs", "list", "--status", "done", "--json", env=db_env(tmp_path))
    assert json.loads(proc.stdout)["handoffs"] == []


# -- init -------------------------------------------------------------------------


def test_init_creates_env_in_cwd_and_masks_secrets(tmp_path):
    proc = run_cli(
        "init", "--api-key", "sk-test-secret-value", "--github-repo", "owner/repo", "--json",
        cwd=tmp_path,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "success"
    assert payload["created"] is True
    assert set(payload["updated"]) == {"GOOGLE_API_KEY", "GITHUB_DEMO_REPO"}
    assert payload["values"]["GOOGLE_API_KEY"] == "***"

    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "GOOGLE_API_KEY=sk-test-secret-value" in env_text
    assert "GITHUB_DEMO_REPO=owner/repo" in env_text
    # Secrets never echo back to either stream.
    assert "sk-test-secret-value" not in proc.stdout
    assert "sk-test-secret-value" not in proc.stderr


def test_init_is_idempotent_and_only_overwrites_passed_flags(tmp_path):
    target = tmp_path / "proj"
    target.mkdir()
    first = run_cli("init", "--dir", str(target), "--github-repo", "owner/repo", "--json")
    assert first.returncode == 0, first.stderr

    # Re-run with NO flags: nothing changes.
    second = run_cli("init", "--dir", str(target), "--json")
    assert second.returncode == 0, second.stderr
    payload = json.loads(second.stdout)
    assert payload["created"] is False
    assert payload["updated"] == []
    assert "GITHUB_DEMO_REPO=owner/repo" in (target / ".env").read_text(encoding="utf-8")

    # Re-run WITH the flag: that one key (and only it) is overwritten.
    third = run_cli("init", "--dir", str(target), "--github-repo", "other/repo", "--json")
    assert third.returncode == 0, third.stderr
    env_text = (target / ".env").read_text(encoding="utf-8")
    assert "GITHUB_DEMO_REPO=other/repo" in env_text
    assert "GITHUB_DEMO_REPO=owner/repo" not in env_text
