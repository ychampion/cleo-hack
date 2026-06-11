"""Skill tools + skills index tests (CONTRACTS §11). No network/LLM."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import mcp_server.skill_tools as st  # noqa: E402
from mcp_server import server as srv  # noqa: E402


def _load_agents_skills_index():
    """Import agents/cleo/skills_index.py directly from its file path.

    Importing it as ``agents.cleo.skills_index`` would trigger
    ``agents/cleo/__init__.py`` -> agent.py -> the whole ADK tree; the module
    is deliberately standalone, so load it standalone.
    """
    path = REPO_ROOT / "agents" / "cleo" / "skills_index.py"
    spec = importlib.util.spec_from_file_location("cleo_skills_index_for_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


agents_skills_index = _load_agents_skills_index()

AUTHORED_SKILL = """---
name: demo-skill
description: Use when demonstrating the skill store in tests.
---

# Demo skill

1. Call `list_feedback`.
2. Reply with counts.
"""

LEARNED_SKILL = """---
name: learned-trick
description: "Use when a learned procedure is needed: quotes, colons and all."
---

1. Do the learned thing.
"""

CONTRACT_AUTHORED_NAMES = {
    "triage-feedback",
    "write-weekly-brief",
    "escalate-churn-risk",
    "fix-from-feedback",
    "answer-with-evidence",
}


@pytest.fixture()
def tmp_skills(tmp_path, monkeypatch) -> Path:
    """A tmp skills root with one authored and one learned skill."""
    root = tmp_path / "skills"
    (root / "demo-skill").mkdir(parents=True)
    (root / "demo-skill" / "SKILL.md").write_text(AUTHORED_SKILL, encoding="utf-8")
    (root / "learned" / "learned-trick").mkdir(parents=True)
    (root / "learned" / "learned-trick" / "SKILL.md").write_text(
        LEARNED_SKILL, encoding="utf-8"
    )
    monkeypatch.setenv("CLEO_SKILLS_DIR", str(root))
    return root


def test_skill_tools_are_registered_on_the_shared_mcp_instance():
    registered = {t.name for t in asyncio.run(srv.mcp.list_tools())}
    assert {"list_skills", "load_skill", "save_skill"} <= registered


# -- list_skills / skills_index ---------------------------------------------------


def test_list_skills_merges_authored_and_learned(tmp_skills):
    result = st.list_skills()
    assert result["status"] == "success"
    by_name = {s["name"]: s for s in result["skills"]}
    assert by_name["demo-skill"]["source"] == "authored"
    assert by_name["learned-trick"]["source"] == "learned"
    assert by_name["demo-skill"]["description"].startswith("Use when demonstrating")
    # Quoted frontmatter description round-trips unquoted.
    assert by_name["learned-trick"]["description"].startswith("Use when a learned procedure")
    # list entries are index-only: no body field.
    assert "body" not in by_name["demo-skill"]


def test_learned_skill_never_shadows_an_authored_one(tmp_skills):
    # A name clash created manually on disk (save_skill would reject it).
    clash = tmp_skills / "learned" / "demo-skill"
    clash.mkdir(parents=True)
    (clash / "SKILL.md").write_text(
        '---\nname: demo-skill\ndescription: "impostor"\n---\n\nshadow body\n',
        encoding="utf-8",
    )
    sources = [s["source"] for s in st.skills_index() if s["name"] == "demo-skill"]
    assert sources == ["authored", "learned"]  # both listed, authored first
    # load_skill resolves the authored one.
    loaded = st.load_skill("demo-skill")
    assert loaded["status"] == "success"
    assert "Demo skill" in loaded["body"]


def test_skills_index_empty_when_root_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("CLEO_SKILLS_DIR", str(tmp_path / "nowhere"))
    assert st.skills_index() == []
    assert st.list_skills() == {"status": "success", "skills": []}


# -- load_skill --------------------------------------------------------------------


def test_load_skill_found_authored_and_learned(tmp_skills):
    authored = st.load_skill("demo-skill")
    assert authored["status"] == "success"
    assert authored["name"] == "demo-skill"
    assert authored["body"].startswith("# Demo skill")
    learned = st.load_skill("learned-trick")
    assert learned["status"] == "success"
    assert "Do the learned thing" in learned["body"]


def test_load_skill_missing(tmp_skills):
    result = st.load_skill("no-such-skill")
    assert result["status"] == "error"
    assert "not found" in result["message"]


@pytest.mark.parametrize("name", ["../demo-skill", "a/b", "a\\b", "demo skill", ""])
def test_load_skill_rejects_unsafe_names(tmp_skills, name):
    assert st.load_skill(name)["status"] == "error"


# -- save_skill --------------------------------------------------------------------


def test_save_skill_happy_path(tmp_skills):
    result = st.save_skill(
        "rotate-api-keys",
        'Use when rotating keys: includes "verify" step.',
        "1. Rotate.\n2. Verify.",
    )
    assert result == {"status": "success", "name": "rotate-api-keys"}
    path = tmp_skills / "learned" / "rotate-api-keys" / "SKILL.md"
    assert path.is_file()
    loaded = st.load_skill("rotate-api-keys")
    assert loaded["status"] == "success"
    assert loaded["description"] == 'Use when rotating keys: includes "verify" step.'
    assert loaded["body"] == "1. Rotate.\n2. Verify."
    assert any(
        s["name"] == "rotate-api-keys" and s["source"] == "learned"
        for s in st.skills_index()
    )


@pytest.mark.parametrize(
    "bad_name",
    [
        "../x",
        "a/b",
        "a\\b",
        "..",
        "UPPER-case",
        "has_underscore",
        "-leading",
        "trailing-",
        "double--hyphen",
        "spaced name",
        "",
        "x" * 65,
    ],
)
def test_save_skill_rejects_bad_names(tmp_skills, bad_name):
    result = st.save_skill(bad_name, "desc", "body")
    assert result["status"] == "error"
    # Nothing escaped or landed under learned/ for traversal-shaped names.
    learned_entries = [
        p.name for p in (tmp_skills / "learned").iterdir() if p.is_dir()
    ]
    assert learned_entries == ["learned-trick"]
    assert not (tmp_skills.parent / "x").exists()


def test_save_skill_rejects_authored_collision(tmp_skills):
    result = st.save_skill("demo-skill", "desc", "body")
    assert result["status"] == "error"
    assert "authored" in result["message"]
    assert not (tmp_skills / "learned" / "demo-skill").exists()


def test_save_skill_overwrites_learned(tmp_skills):
    assert st.save_skill("learned-trick", "v2 description", "v2 body")["status"] == "success"
    loaded = st.load_skill("learned-trick")
    assert loaded["description"] == "v2 description"
    assert loaded["body"] == "v2 body"


@pytest.mark.parametrize(
    ("description", "body"),
    [("", "body"), ("   ", "body"), ("desc", ""), ("desc", "   ")],
)
def test_save_skill_requires_description_and_body(tmp_skills, description, body):
    assert st.save_skill("valid-name", description, body)["status"] == "error"
    assert not (tmp_skills / "learned" / "valid-name").exists()


def test_save_skill_collapses_multiline_description(tmp_skills):
    assert st.save_skill("multi-line", "line one\nline two", "body")["status"] == "success"
    loaded = st.load_skill("multi-line")
    assert loaded["description"] == "line one line two"


# -- agents/cleo/skills_index.render_skills_index -----------------------------------


def test_render_skills_index_lists_skills_and_auto_use_rule(tmp_skills):
    rendered = agents_skills_index.render_skills_index()
    assert rendered.startswith("Available skills:")
    assert "- demo-skill: Use when demonstrating the skill store in tests." in rendered
    assert "- learned-trick:" in rendered
    for phrase in ("list_skills", "load_skill", "save_skill", "never save secrets"):
        assert phrase in rendered


def test_render_skills_index_neutralizes_adk_placeholders(tmp_skills):
    st.save_skill("braces-skill", "uses {state} braces", "body")
    rendered = agents_skills_index.render_skills_index()
    assert "{" not in rendered and "}" not in rendered
    assert "- braces-skill: uses (state) braces" in rendered


def test_render_skills_index_empty_when_no_skills(tmp_path, monkeypatch):
    monkeypatch.setenv("CLEO_SKILLS_DIR", str(tmp_path / "empty"))
    assert agents_skills_index.render_skills_index() == ""


# -- the real authored skills (repo skills dir, READ-ONLY) ---------------------------


@pytest.fixture()
def repo_skills(monkeypatch):
    monkeypatch.setenv("CLEO_SKILLS_DIR", str(REPO_ROOT / "skills"))


def test_repo_has_exactly_the_five_contract_skills(repo_skills):
    authored = {s["name"] for s in st.skills_index() if s["source"] == "authored"}
    assert authored == CONTRACT_AUTHORED_NAMES


def test_repo_authored_skills_parse_with_real_content(repo_skills):
    for name in CONTRACT_AUTHORED_NAMES:
        skill = st.load_skill(name)
        assert skill["status"] == "success", f"{name} failed to load"
        assert skill["name"] == name
        # description: one trigger-phrased line.
        assert skill["description"].strip(), f"{name} has an empty description"
        assert "\n" not in skill["description"]
        assert skill["description"].lower().startswith("use when")
        # body: a real numbered runbook that names MCP tools.
        assert "1." in skill["body"], f"{name} body has no numbered procedure"
        assert "`" in skill["body"], f"{name} body names no tools"
        assert len(skill["body"].splitlines()) >= 20, f"{name} body is too thin"


def test_repo_skill_index_renders_for_agent_instructions(repo_skills):
    rendered = agents_skills_index.render_skills_index()
    for name in CONTRACT_AUTHORED_NAMES:
        assert f"- {name}: " in rendered
    # Safe for ADK instruction injection (no placeholder braces).
    assert "{" not in rendered and "}" not in rendered
