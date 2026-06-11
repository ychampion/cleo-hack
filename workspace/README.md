# workspace/ — the repo Cleo's coder operates on in the demo

This directory is the **only** filesystem surface the `coder` sub-agent can touch
(its tools resolve every path under `workspace/` and reject anything that escapes).
`lumen_checkout/` is Lumen's tiny billing service, carrying the v2.3 volume-pricing
regression described in the feedback corpus: business-plan checkouts above 10 seats
hit a missing tier-pricing key and 500. `lumen_checkout/tests/` is the acceptance
suite — it fails on the seeded bug and passes once the coder lands the fix
(the coder runs it via `run_workspace_tests`; the main repo suite never collects it).

Reset after a demo run: `git checkout -- workspace/`
