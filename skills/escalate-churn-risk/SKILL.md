---
name: escalate-churn-risk
description: Use when urgent feedback (churn threat, outage, urgency >= 2) may warrant filing a GitHub issue.
---

# Escalate a churn risk to GitHub

Filing an issue is a real-world write. It happens only under directive, only
with evidence, and always on the ledger.

## Procedure

1. **Directive check first.** Call `get_directives`. Proceed only if an
   ACTIVE directive explicitly covers escalation (mentions "escalate"). No
   such directive → stop and call `record_action` with {type: "escalation",
   status: "skipped", rationale: "no active escalation directive",
   evidence_ids: [the fb_ ids]}.
2. **Pick ONE target.** From `list_themes` / `list_bets`, choose the single
   most urgent theme with urgency >= 2 AND a concrete churn signal
   (cancel/switch language, blocked revenue) in its evidence. One issue per
   pass — never bulk-file.
3. **Collect evidence.** Use `search_feedback` / `list_feedback` to pull the
   theme's items; pick the 2–3 strongest quotes. Every quote keeps its fb_ id.
4. **Dedupe.** Call `search_issues` (or `list_issues`) for an open issue
   matching the theme title. If one exists, call `add_issue_comment` with
   ONLY the new evidence instead of filing a duplicate.
5. **File.** Call `create_issue` on the repo from `GITHUB_DEMO_REPO`:
   - title: `[Cleo] <theme title>`
   - body: a short problem statement; `## Evidence` quoting each item with
     its fb_ id verbatim; `## Impact` (urgency, churn risk, affected
     accounts); footer `_Filed autonomously by Cleo under directive._`
6. **Respect the guard.** Every GitHub write passes a policy guard:
   - status "blocked" → do NOT retry, rephrase, or work around it; the block
     and its reasons are already on the ledger. Report it and move on.
   - allowed writes are auto-recorded — NEVER call `record_action` yourself
     for a GitHub write (it would double-count the ledger).
7. **Unconfigured GitHub** (no token or repo): escalation is impossible —
   call `record_action` ONCE with {type: "escalation", status: "skipped",
   target: "github (unconfigured)", rationale: why it deserved escalation,
   evidence_ids: [the fb_ ids]} so the need survives on the ledger.
8. **Reply** with: the issue URL (or blocked/skipped plus reason), the
   directive quoted, and the evidence ids used.

## Quality bar

- The issue body must be readable by an engineer with zero Cleo context.
- Evidence is verbatim user language; your interpretation lives only in the
  problem statement.
- One escalation per pass; the next pass can file the next one.
