---
name: write-weekly-brief
description: Use when asked to write, update, or refresh the weekly product brief.
---

# Write the weekly brief

One page, evidence-first, for a founder with 90 seconds.

## Procedure

1. **Gather state** — call all of: `list_themes`, `list_bets`, `list_actions`
   (no status filter; you need executed AND blocked/skipped), and
   `get_latest_brief` (for week-over-week comparison).
2. **Compose markdown in EXACTLY this order:**
   - `# Product Brief — <ISO week>` (e.g. `2026-W24`).
   - `## Urgent` — every theme with urgency >= 2, one line each:
     `**<title>** — <n> items, urgency <u> (<th_ id>)`. If none, write
     "Nothing at urgency 2+ this week."
   - `## Themes` — top 5 by urgency then evidence count, each with trend
     (new/rising/steady) and a one-line summary. Compare against the previous
     brief: call out themes that are new or escalated since last week.
   - `## Bets` — each proposed bet: title, impact/effort/confidence, and its
     evidence_ids. Order by impact desc, then effort asc.
   - `## Contradictions` — conflicting asks with both fb_ ids and a one-line
     framing of the tradeoff. Omit the section only when there are none.
   - `## Actions Taken` — from `list_actions`: issues filed (with target),
     escalations blocked/skipped (with reason), briefs written. The ledger is
     the source of truth here, not memory.
3. **Quality bar before saving:**
   - Every number traces to a tool result from step 1; never estimate.
   - Every theme/bet line carries its id; quotes (max 2 total) are verbatim.
   - The whole brief stays within ~40 lines of markdown.
4. **Save** with `write_brief(markdown, theme_ids=[every th_ id mentioned])`.
5. **Ledger it**: call `record_action` ONCE with type "brief", status
   "executed", target = the returned br_ id, and a rationale quoting the
   directive you are acting under.
6. **Reply** with the br_ id and a 2-line summary of what changed vs last
   week (new urgent themes, bets added, escalations).

## Failure handling

- `write_brief` returns an error → fix the arguments (markdown non-empty,
  theme_ids a list) and retry once. Do NOT `record_action` for a brief that
  never saved.
- No themes in the store → say so and suggest a triage run instead of
  writing an empty brief.
