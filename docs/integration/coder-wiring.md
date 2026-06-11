# Coder wiring — exact lines for `agents/cleo/agent.py`

Four verbatim edits integrate the §12 coder into the operator. Nothing else
changes. (This doc exists because `agent.py` is owned by the integration pass;
the coder itself — `agents/cleo/sub_agents/coder.py`, `agents/cleo/coder_tools.py`
— is already built and tested.)

## 1. Import

Directly below the existing `from .sub_agents import (…)` block, add:

```python
from .sub_agents.coder import make_coder  # noqa: E402
```

(`make_coder` is intentionally NOT re-exported from `sub_agents/__init__.py` to
avoid a parallel-edit collision; move it there later if you prefer the package
convention.)

## 2. Operator store tools

In `cleo_operator`'s `make_store_toolset([...])` list, replace:

```python
                "get_latest_brief",
                "get_directives",
```

with:

```python
                "get_latest_brief",
                "get_directives",
                "create_handoff",
                "list_handoffs",
```

## 3. Sub-agents

Replace:

```python
    sub_agents=[triage_pipeline, watch_loop],
```

with:

```python
    sub_agents=[triage_pipeline, watch_loop, make_coder()],
```

(If the coder ever needs a second tree position — e.g. inside a loop — use the
factory's `suffix` argument like every other stage: `make_coder("_w")`.)

## 4. Operator instruction — dispatch-to-coder paragraph

Append this paragraph to the END of `cleo_operator`'s `instruction` string
(after the Directives paragraph, before the closing `"""`):

```text

Dispatching code fixes — when the user asks you to FIX something in code (or
the `fix-from-feedback` skill applies): call `list_handoffs` first; if no open
handoff covers the problem, call `create_handoff` ONCE with the bet's problem
statement, its fb_ evidence_ids, and concrete testable acceptance criteria
(e.g. "business plan with 12 seats returns HTTP 200"). Then transfer to
`coder`, ALWAYS stating the handoff id explicitly in your message to it —
"Work handoff hf_… to completion" (the coder also reads session state key
"handoff_id" when a caller sets it, but the id in the message is the channel
that always works). The coder edits only files under workspace/, proves the
fix by running the workspace test suite, closes the handoff, and records its
own "code_fix" action — never record one on its behalf.
```

## Verify after applying

```bash
uv run python -c "from agents.cleo.agent import root_agent; print([a.name for a in root_agent.sub_agents])"
# expect: ['triage_pipeline', 'watch_loop', 'coder']
uv run pytest -q                 # 121+ passing, no network
uv run python scripts/demo_fix_loop.py   # live (GOOGLE_API_KEY): full fix loop
git checkout -- workspace/               # reset the demo bug afterwards
```
