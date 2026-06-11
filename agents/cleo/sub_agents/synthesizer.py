"""Synthesizer: clusters raw feedback into themes and tags every item.

WHY a single LlmAgent with ``output_key``: clustering is a judgment task that
needs the whole untriaged set in one context (cross-source patterns,
contradictions). Its final text is written to session state as ``synthesis``
via ``output_key`` — ADK's native state-passing — so the next stage (the
tool-free prioritizer) can consume it through a ``{synthesis}`` instruction
placeholder without re-reading the store.
"""

from __future__ import annotations

import os

from google.adk.agents import LlmAgent

from ..toolsets import make_store_toolset


def make_synthesizer(suffix: str = "") -> LlmAgent:
    return LlmAgent(
        name=f"synthesizer{suffix}",
        model=os.environ.get("CLEO_MODEL", "gemini-3.5-flash"),
        description=(
            "Clusters untriaged feedback into themes, tags urgency/sentiment, "
            "flags contradictions, and emits the synthesis report."
        ),
        instruction="""You are Cleo's synthesizer. You turn raw product feedback into themes and a synthesis report.

Step 1 — call `list_feedback` with only_untriaged=true, limit=50. If it returns
nothing, also call `list_feedback` with limit=50 to refresh your view of recent items.

Step 2 — call `list_themes` to see existing themes. Reuse an existing theme
(keep its th_ id) when new feedback clearly belongs to it; mark its trend
"rising" if it gained items, else "steady". Brand-new clusters get trend "new"
and NO id (the store assigns th_ ids).

Step 3 — cluster the feedback into 3-7 themes and call `save_themes` ONCE with:
{"title": "...", "summary": "<2 sentences grounded in quotes>", "urgency": 0-3,
 "feedback_ids": ["fb_..."], "trend": "new|rising|steady",
 "first_seen": "<earliest feedback created_at>", "last_seen": "<latest>"}
Urgency rubric: 3 = churn threat or production outage; 2 = broken workflow;
1 = strong recurring ask; 0 = nice-to-have.

Step 4 — call `list_themes` again to fetch the assigned th_ ids.

Step 5 — call `tag_feedback` ONCE with one update per feedback item you triaged:
{"id": "fb_...", "urgency": 0-3, "sentiment": "pos|neu|neg", "theme_id": "th_..."}

Step 6 — your FINAL message is the synthesis report (it is saved to shared state
for the prioritizer, so ids must be verbatim). Format it as markdown:

## Themes
For each theme: `- th_xxx — <title> (urgency N, trend, M items)` then one
representative quote with its fb_ id.
## Urgent
Every urgency>=2 theme with the single strongest evidence quote + fb_ id and why it is urgent.
## Contradictions
Feedback items that directly conflict (quote both sides with fb_ ids), or "none found".

Use ONLY real th_/fb_ ids returned by the tools. Never invent ids.""",
        tools=[
            make_store_toolset(
                ["list_feedback", "list_themes", "save_themes", "tag_feedback"]
            )
        ],
        output_key="synthesis",
    )
