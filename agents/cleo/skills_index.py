"""Static skills index embedded into agent instructions (CONTRACTS §11).

``render_skills_index()`` is called once at agent-construction time and its
output is appended to the operator and actor instructions: the cheap
"what skills exist" menu is static, while ``load_skill`` remains the dynamic
path for the full procedure body.

Decoupling note: this module deliberately DUPLICATES the ~20-line frontmatter
reader from ``mcp_server/skill_tools.py`` instead of importing it. ``agents/``
must stay importable without ``mcp_server`` on the path (the store is reached
over MCP, never in-process), and the duplicated logic is trivial and pinned by
``tests/test_skills.py`` on both sides.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

AUTO_USE_RULE = (
    "Before any multi-step task, call `list_skills` and, if a skill matches the "
    "task, call `load_skill` and follow its procedure step by step. After "
    "succeeding at a multi-step task no skill covered, call `save_skill` with a "
    "reusable, generalized procedure — never save secrets, ids, or one-off details."
)


def _skills_root() -> Path:
    """Same resolution as mcp_server.skill_tools: env CLEO_SKILLS_DIR else <repo>/skills."""
    raw = os.environ.get("CLEO_SKILLS_DIR", "").strip()
    return Path(raw) if raw else _REPO_ROOT / "skills"


def _read_meta(skill_dir: Path) -> tuple[str, str] | None:
    """Return (name, description) from a skill dir's SKILL.md frontmatter, or None."""
    path = skill_dir / "SKILL.md"
    try:
        if not path.is_file():
            return None
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    if not lines or lines[0].strip() != "---":
        return None
    meta: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return meta.get("name") or skill_dir.name, meta.get("description", "")
        key, sep, value = line.partition(":")
        if not sep:
            continue
        value = value.strip()
        if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
            try:
                value = json.loads(value)
            except ValueError:
                pass
        meta[key.strip()] = value
    return None  # unterminated frontmatter


def render_skills_index() -> str:
    """Compact 'Available skills' block + auto-use rule, or "" when none exist.

    ADK treats ``{...}`` in instructions as state-placeholder injection, so
    braces in descriptions (possible in learned skills) are neutralized.
    """
    entries: list[tuple[str, str]] = []
    root = _skills_root()
    for base in (root, root / "learned"):
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if not child.is_dir() or (base == root and child.name == "learned"):
                continue
            meta = _read_meta(child)
            if meta is not None:
                entries.append(meta)
    if not entries:
        return ""
    lines = ["Available skills:"]
    for name, description in entries:
        safe_desc = description.replace("{", "(").replace("}", ")")
        lines.append(f"- {name}: {safe_desc}")
    return "\n".join(lines) + "\n\n" + AUTO_USE_RULE
