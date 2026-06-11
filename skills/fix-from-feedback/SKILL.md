---
name: fix-from-feedback
description: Use when asked to fix the bug behind a bet or theme — hand off to the coder subagent and verify the result.
---

# Fix from feedback (bet → coder handoff → verified fix)

The closed loop: evidence picks the bug, a handoff scopes it, the coder fixes
it in `workspace/`, tests prove it, the ledger records it.

## Procedure

1. **Pick the bet.** Call `list_bets` and select the target (the one the user
   named, else highest urgency then impact). It must have evidence_ids — a
   fix without evidence is out of scope.
2. **Re-read the evidence.** Use `search_feedback` / `list_feedback` on the
   bet's evidence_ids so the handoff describes observed behavior, not the
   bet's paraphrase of it.
3. **Check for an open handoff.** Call `list_handoffs(status="open")` and
   `list_handoffs(status="in_progress")` — if one already covers this bet,
   resume it instead of creating a duplicate.
4. **Create the handoff.** Call `create_handoff` with:
   - `bet_id` and an imperative `title`
     ("Fix checkout 500 for business plans over 10 seats"),
   - `problem`: symptom + reproduction in 2–4 sentences, citing fb_ ids,
   - `evidence_ids`: the fb_ ids from step 2,
   - `acceptance`: testable bullets — ALWAYS include "run_workspace_tests
     passes" plus the specific behavior (e.g. "POST /billing/checkout with
     plan=business, seats=12 returns 200").
5. **Transfer to `coder`** with the returned hf_ id placed in session state
   key `handoff_id`. The coder reads the workspace, makes the SMALLEST fix
   satisfying acceptance, runs tests until green, and calls `update_handoff`
   itself. Do not micro-manage its edits.
6. **Verify on return.** Call `get_handoff(id)` and trust only the stored
   record:
   - status "done" AND result.tests shows passing → proceed.
   - status "failed", or tests not green → nothing is fixed; go to step 7
     with the failure.
7. **Ledger the outcome.** Call `record_action` with type "code_fix":
   - on done: status "executed", target = the hf_ id, payload
     {files_changed: result.files_changed}, evidence_ids from the handoff,
     rationale linking bet → fix.
   - on failed: status "failed", rationale = result.notes — a failure must be
     as auditable as a success.
8. **Report**: handoff id, files_changed, the test summary line, and the bet
   it closes. Suggest marking the bet "shipped" only after human review.

## Failure handling

- Coder reports failed → record it (step 7), surface result.notes verbatim,
  and propose ONE next step (sharper acceptance criteria, or human
  takeover). Never retry in a loop.
- `create_handoff` returns an error → fix the shape (acceptance must be a
  non-empty list) and retry once.
- Never edit workspace files yourself — only the coder has workspace tools.
