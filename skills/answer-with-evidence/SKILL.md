---
name: answer-with-evidence
description: Use when answering any operator question about feedback, themes, bets, actions, briefs, or directives.
---

# Answer with evidence

Every claim carries an id, a count, or a verbatim quote. If the store does
not say it, you do not say it.

## Tool routing by question type

1. "How are we doing / what's the state?" → `get_overview` first; drill into
   specifics only if asked.
2. "What are people saying about X?" → `search_feedback(query="X")`; quote
   2–3 items verbatim with their fb_ ids and authors.
3. "What's new / untriaged?" → `list_feedback(only_untriaged=true)`; report
   the count and a one-line sample.
4. "What's urgent / our biggest problems?" → `list_themes`; present urgency
   >= 2 themes first, each with its evidence count and th_ id.
5. "What should we build / priorities?" → `list_bets`; give title,
   impact/effort/confidence, and evidence_ids. Bets ARE the recommendation —
   do not improvise new ones while answering.
6. "What has Cleo done?" → `list_actions` (filter by status if asked); the
   ledger is the only honest answer — include blocked and skipped entries.
7. "What's in the brief?" → `get_latest_brief`; summarize ITS content, do
   not regenerate it (that is the `write-weekly-brief` skill).
8. "What are your standing orders?" → `get_directives`; quote them verbatim.

## Answer format

- Lead with the direct answer in one sentence, then the evidence lines.
- Cite every entity by id (fb_/th_/bet_/act_/br_/dir_) on first mention;
  counts come from tool results, never from memory.
- Quotes are verbatim and attributed ("@dana, slack, fb_…").
- 8 lines maximum unless the user asked for a full dump.

## Hard rules (failure handling)

- A tool returns an empty list → say exactly that ("0 untriaged items");
  never fabricate plausible examples.
- A tool returns `"status": "error"` → report the message; do not guess at
  what the data probably is.
- The question needs fresh data ("new", "latest", "today") and the store
  looks stale → answer from current data AND offer a triage run; never
  silently run the pipeline.
- A multi-step request hiding inside a question ("can you also file…") →
  switch to the matching skill (`escalate-churn-risk`, `fix-from-feedback`)
  instead of acting ad hoc.
