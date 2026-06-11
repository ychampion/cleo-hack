# CS weekly notes — week of 2026-06-08

Date: 2026-06-08
Owner: Maya Chen (Lumen CS)
Internal customer-success sync notes. Shared with product every Monday.

## At-risk accounts: checkout 500s are now a churn driver

The v2.3 billing regression is the worst week of tickets since launch: 23 checkout-related tickets, all failing on POST /billing/checkout. Acme Robotics (60 seats) has CFO-level pressure and is actively pricing Linear + Geckoboard; their deadline is Friday June 12. Brightloop (42 seats) ties it directly to next month's renewal. Ridgeview can't upgrade before their June 17 board meeting. Karta was CHARGED without receiving the upgrade — payments incident territory. Every day this stays broken we are converting our most expansion-ready customers into churn risks.

## SSO escalations: one bug, three enterprise accounts

Nordwind Labs (180 seats, go/no-go June 13), Helix Manufacturing (200-seat prospect, deadline June 30) and Fathom Health IT are all blocked by the same "invalid certificate chain" error when uploading Okta SAML metadata. Nordwind's IT lead diagnosed it credibly: our parser appears to reject metadata containing an intermediate certificate, which is standard after a cert rotation. Stripping the intermediate makes login fail later, so there is no workaround. Two contracts and one rollout hang on what looks like one XML parsing fix.

## Feature ask roundup: CSV export and webhooks keep climbing

CSV export is now the most-requested feature on record: Acme, Quill, Pebble, Fathom, Ridgeview and Brightloop all asked again this cycle — mostly finance/ops needing report numbers in spreadsheets, with one transcription error already caused by manual retyping. Webhooks/bulk API is the quieter twin: Ridgeview, Karta and Nordwind want events pushed to their warehouses, and Sam logged a lost 120-seat fintech deal where missing webhooks was the stated no-go.

## Onboarding: the empty-dashboard cliff

Pattern across Quill, Pebble, Fathom and a churned trial (Loop Studio): people connect integrations, see an empty dashboard with no explanation of the ~24h backfill, and conclude the product is broken. Loop Studio's trial expired before their data ever appeared. Separately, the invite flow is buried in Settings > Members — Fathom accidentally created a duplicate workspace for their second team. Cheap fixes (a backfill banner, a visible Invite button) for expensive first impressions.

## Notifications: customers directly contradict each other on digest defaults

Genuine conflict to flag for product. Brightloop (Hannah) and Pebble (Owen) want the weekly email digest ON by default — their teams missed sprint-health alerts because nobody enabled it. Karta (Milo, plus an IT report from Ruth) want it OFF by default and call default-on hostile; one analyst reported the digest as phishing. We cannot satisfy both with a single default; suggested direction from CS is a workspace-level admin toggle, which Hannah explicitly endorsed at the QBR.
