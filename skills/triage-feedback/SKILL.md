---
name: triage-feedback
description: Use when asked to triage, run, or process new feedback — the full ingest → tag → cluster → bet → act pass.
---

# Triage feedback (full pipeline)

Objective: every untriaged feedback item ends the pass tagged, clustered into
a theme, and reflected in evidence-backed bets — with all side effects on the
ledger.

## Procedure

1. **Scope the work.** Call `list_feedback` with `only_untriaged=true`. If it
   returns nothing and no source has new items, stop and report "no new
   signal" — do not re-cluster what is already triaged.
2. **Ingest new raw items** from every available source connector, then write
   them with ONE `ingest_feedback` call per source batch. Map each item to the
   contract shape: `source` in github|intercom|slack|call|doc, `external_id`
   (the dedupe key — always set it), `author`, `text` verbatim (never
   summarize at ingest), `url` when known. Duplicates are expected and
   harmless; the store skips them.
3. **Tag every untriaged item** with `tag_feedback` (batch the updates):
   - `urgency` rubric — 3: outage, data loss, or explicit churn threat
     ("canceling", "switching"); 2: blocking bug or broken integration with
     no workaround; 1: real friction or a repeated request; 0: nice-to-have
     or praise.
   - `sentiment`: pos|neu|neg from the text itself, not from the topic.
4. **Cluster into themes** and upsert with `save_themes`. Quality bar:
   - 3–8 themes total; merge near-duplicates, split only on different root
     causes.
   - Title states the user's problem ("Checkout 500s on business plans"),
     never a solution ("Fix pricing lookup").
   - `feedback_ids` lists every supporting fb_ id; one weak item is not a
     theme — leave it tagged but unclustered.
   - Theme `urgency` = max urgency of its evidence; `trend` is "rising" only
     when new items joined an existing theme this pass.
5. **Surface contradictions.** When two items demand opposite behavior, keep
   both fb_ ids in the theme summary and name the conflict explicitly —
   never silently pick a side.
6. **Propose bets** and persist with `save_bets`: each bet cites at least 2
   `evidence_ids` (1 is acceptable only for an urgency-3 outage), links its
   `theme_ids`, and scores impact/effort 1–5 with honest `confidence`
   (cap at 0.9). No evidence → no bet; drop it.
7. **Act under directives.** Call `get_directives`. If escalation is ordered
   and warranted, follow the `escalate-churn-risk` skill; if the brief must
   stay current, follow `write-weekly-brief`.
8. **Report**: counts (ingested, tagged, themes, bets, actions), the single
   most urgent theme with its evidence count, and anything skipped plus why.

## Failure handling

- A tool returns `"status": "error"` → fix the arguments and retry ONCE; if
  it still fails, continue the pass and put the failure in the report.
- Never invent fb_/th_/bet_ ids — use only ids returned by tools.
