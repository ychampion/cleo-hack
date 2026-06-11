# Skills wiring (CONTRACTS §11) — apply verbatim

How to wire the skill system into the operator and actor. Three changes per
agent: (1) embed the rendered skill index in the instruction, (2) extend the
store-toolset `tool_filter`, (3) nothing else — `list_skills`/`load_skill`/
`save_skill` are ordinary store-server tools, so no new toolset or callback
is needed.

The auto-use rule itself ships INSIDE `render_skills_index()` (constant
`AUTO_USE_RULE` in `agents/cleo/skills_index.py`), so embedding the index
embeds the rule — do not paste the rule text a second time.

---

## 1. Operator (`agents/cleo/agent.py`)

### 1a. Import (top of file, with the other `.`-relative imports)

```python
from .skills_index import render_skills_index  # noqa: E402
```

### 1b. One-line instruction change

The `cleo_operator` `instruction=` argument currently ends with
`...you cannot create directives yourself."""`. Append the rendered index:

```python
    instruction="""You are Cleo, an autonomous product-feedback operator for a startup team.
...existing text unchanged...
add it on the Directives page — you cannot create directives yourself."""
    + "\n\n"
    + render_skills_index(),
```

With the five authored skills present, that appends exactly this text block
(learned skills will add lines as they are saved; the index is rendered at
agent-construction time, so a process restart picks them up):

```
Available skills:
- answer-with-evidence: Use when answering any operator question about feedback, themes, bets, actions, briefs, or directives.
- escalate-churn-risk: Use when urgent feedback (churn threat, outage, urgency >= 2) may warrant filing a GitHub issue.
- fix-from-feedback: Use when asked to fix the bug behind a bet or theme — hand off to the coder subagent and verify the result.
- triage-feedback: Use when asked to triage, run, or process new feedback — the full ingest → tag → cluster → bet → act pass.
- write-weekly-brief: Use when asked to write, update, or refresh the weekly product brief.

Before any multi-step task, call `list_skills` and, if a skill matches the task, call `load_skill` and follow its procedure step by step. After succeeding at a multi-step task no skill covered, call `save_skill` with a reusable, generalized procedure — never save secrets, ids, or one-off details.
```

### 1c. Store-toolset tool_filter

In the operator's `make_store_toolset([...])` call, the filter list grows by
three entries — it becomes:

```python
        make_store_toolset(
            [
                "list_feedback",
                "search_feedback",
                "list_themes",
                "list_bets",
                "list_actions",
                "get_latest_brief",
                "get_directives",
                "list_skills",
                "load_skill",
                "save_skill",
            ]
        )
```

---

## 2. Actor (`agents/cleo/sub_agents/actor.py`)

### 2a. Import (top of file, with the other `..`-relative imports)

```python
from ..skills_index import render_skills_index
```

### 2b. One-line instruction change

Inside `make_actor`, the `instruction=f"""..."""` currently ends with
`...reply `no new signal — watch loop done.`"""`. Append the rendered index
the same way:

```python
        instruction=f"""You are Cleo's actor. ...existing f-string unchanged...
bets AND no actions, call `exit_loop` and reply `no new signal — watch loop done.`"""
        + "\n\n"
        + render_skills_index(),
```

(The appended block is the same text shown in 1b. It is concatenated AFTER
the f-string, so its backticked tool names are never interpreted as f-string
or ADK `{placeholder}` syntax — `render_skills_index()` additionally
neutralizes any braces found in skill descriptions.)

### 2c. Store-toolset tool_filter

In the actor's `make_store_toolset([...])` call, the filter list grows by the
same three entries — it becomes:

```python
        make_store_toolset(
            [
                "save_bets",
                "get_directives",
                "record_action",
                "write_brief",
                "get_latest_brief",
                "list_skills",
                "load_skill",
                "save_skill",
            ]
        ),
```

---

## 3. Which tool_filters change (summary)

| Agent | File | Add to `make_store_toolset([...])` |
|---|---|---|
| `cleo_operator` | `agents/cleo/agent.py` | `"list_skills", "load_skill", "save_skill"` |
| `actor` (via `make_actor`) | `agents/cleo/sub_agents/actor.py` | `"list_skills", "load_skill", "save_skill"` |

No other agent changes: ingestors/synthesizer/prioritizer keep their filters
(they are single-purpose pipeline stages; skill consultation belongs to the
two agents that take open-ended instructions). The coder subagent (§12) keeps
its own filter (`get_handoff`, `update_handoff`) — the `fix-from-feedback`
skill is loaded by the OPERATOR before transferring, not by the coder.

## 4. Sanity check after applying

```bash
uv run pytest tests/test_skills.py -q          # skill store + index + 5 authored skills
uv run python - <<'PY'
from agents.cleo.skills_index import render_skills_index
out = render_skills_index()
assert out.startswith("Available skills:") and "save_skill" in out
print(out)
PY
```

`adk web agents` → ask the operator "what skills do you have?" — it should
answer from the embedded index without any tool call, and call `load_skill`
before its next triage/brief/escalation/fix task.
