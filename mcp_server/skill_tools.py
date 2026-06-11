"""Skill tools — procedural knowledge the agents consult and extend (CONTRACTS §11).

Layout on disk:

    skills/<kebab-name>/SKILL.md            authored, committed, read-only here
    skills/learned/<kebab-name>/SKILL.md    agent-written at runtime via save_skill

``SKILL.md`` = YAML frontmatter (``name``, one-line ``description``) + markdown
body. The frontmatter parser below is intentionally tiny (fenced ``---`` block,
``key: value`` lines) so we carry no YAML dependency; ``save_skill`` only ever
composes frontmatter this parser can read back (descriptions are JSON-quoted,
which is valid YAML, so external YAML readers parse it too).

This module is imported by ``mcp_server.server`` at the bottom of its body and
only REGISTERS tools on the shared ``mcp`` instance — it must not define a
transport or touch the store. ``skills_index()`` is a plain function (not a
tool) for other modules (e.g. the FastAPI ``/api/skills`` route).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from mcp_server.server import mcp, _err

REPO_ROOT = Path(__file__).resolve().parent.parent

# Kebab-case only: lowercase alnum segments joined by single hyphens. This is
# the entire path-traversal defense surface — no '/', '\', '.', or '..' can
# ever match, so a validated name is safe to join onto the learned dir.
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_NAME_LEN = 64


def skills_root() -> Path:
    """Skills root: env ``CLEO_SKILLS_DIR`` (tests) else ``<repo>/skills``."""
    raw = os.environ.get("CLEO_SKILLS_DIR", "").strip()
    return Path(raw) if raw else REPO_ROOT / "skills"


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str] | None:
    """Parse a ``---`` fenced frontmatter block; returns (meta, body) or None."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    meta: dict[str, str] = {}
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            body = "\n".join(lines[i + 1 :]).strip("\n")
            return meta, body
        key, sep, value = line.partition(":")
        if not sep:
            continue
        value = value.strip()
        if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
            try:
                value = json.loads(value)
            except ValueError:
                pass  # keep the raw quoted string; better than dropping it
        meta[key.strip()] = value
    return None  # unterminated frontmatter — not a valid skill file


def _read_skill(skill_dir: Path, source: str) -> dict[str, Any] | None:
    """Read one skill dir into {name, description, body, source}, or None."""
    path = skill_dir / "SKILL.md"
    try:
        if not path.is_file():
            return None
        parsed = _parse_frontmatter(path.read_text(encoding="utf-8"))
    except OSError:
        return None
    if parsed is None:
        return None
    meta, body = parsed
    return {
        "name": meta.get("name") or skill_dir.name,
        "description": meta.get("description", ""),
        "body": body,
        "source": source,
    }


def _scan(base: Path, source: str) -> list[dict[str, Any]]:
    if not base.is_dir():
        return []
    skills = []
    for child in sorted(base.iterdir()):
        # The learned/ subdir is a sibling namespace, not an authored skill.
        if not child.is_dir() or (source == "authored" and child.name == "learned"):
            continue
        skill = _read_skill(child, source)
        if skill is not None:
            skills.append(skill)
    return skills


def skills_index() -> list[dict[str, Any]]:
    """All skills, authored first then learned (plain function, not an MCP tool).

    Both sources are listed even on a name clash — authored skills are never
    shadowed (``load_skill`` resolves authored first; ``save_skill`` rejects
    the clash up front, so clashes only happen via manual file edits).
    """
    root = skills_root()
    return _scan(root, "authored") + _scan(root / "learned", "learned")


@mcp.tool()
def list_skills() -> dict:
    """List every available skill (authored + learned): name, description, source."""
    return {
        "status": "success",
        "skills": [
            {"name": s["name"], "description": s["description"], "source": s["source"]}
            for s in skills_index()
        ],
    }


@mcp.tool()
def load_skill(name: str) -> dict:
    """Load a skill's full step-by-step procedure body by its kebab-case name."""
    if not isinstance(name, str) or not SKILL_NAME_RE.fullmatch(name.strip()):
        return _err("name must be kebab-case (lowercase letters/digits joined by hyphens)")
    name = name.strip()
    root = skills_root()
    for skill_dir, source in ((root / name, "authored"), (root / "learned" / name, "learned")):
        skill = _read_skill(skill_dir, source)
        if skill is not None:
            return {
                "status": "success",
                "name": skill["name"],
                "description": skill["description"],
                "body": skill["body"],
            }
    return _err(f"skill {name!r} not found")


@mcp.tool()
def save_skill(name: str, description: str, body: str) -> dict:
    """Save a learned skill (reusable procedure) under skills/learned/<name>/SKILL.md."""
    if not isinstance(name, str):
        return _err("name must be a string")
    name = name.strip()
    if len(name) > MAX_NAME_LEN:
        return _err(f"name must be at most {MAX_NAME_LEN} characters")
    if not SKILL_NAME_RE.fullmatch(name):
        return _err(
            "name must be kebab-case matching ^[a-z0-9]+(-[a-z0-9]+)*$ "
            "(no slashes, dots, underscores, or uppercase)"
        )
    if not isinstance(description, str) or not description.strip():
        return _err("description is required and must be a non-empty string")
    if not isinstance(body, str) or not body.strip():
        return _err("body is required and must be a non-empty string")

    root = skills_root()
    if (root / name).exists():
        return _err(f"skill {name!r} collides with an authored skill; choose a new name")

    learned_root = (root / "learned").resolve()
    target_dir = (learned_root / name).resolve()
    if target_dir.parent != learned_root:
        # Unreachable after the regex gate; kept as defense in depth.
        return _err("invalid skill name (path traversal rejected)")
    target_dir.mkdir(parents=True, exist_ok=True)

    # Frontmatter is composed, never templated from raw input: the description
    # is whitespace-collapsed to one line and JSON-quoted (valid YAML scalar),
    # so embedded quotes/colons cannot break the frontmatter fence.
    description_line = json.dumps(" ".join(description.split()))
    content = f"---\nname: {name}\ndescription: {description_line}\n---\n\n{body.strip()}\n"
    (target_dir / "SKILL.md").write_text(content, encoding="utf-8")
    return {"status": "success", "name": name}
