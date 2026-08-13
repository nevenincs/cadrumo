---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:00f39b4ea9c37a661af383affb8b7c63d962be9633be189ec832e638bc59e097'
step_id: 'S41'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---




# Rerun the fourteen affected isolated sequence goldens and five owning-page coherence gates after the performance and diagnostic proofs pass, preserving CLI-owned goldens.

## Scope

- `docs/_sequences`
- `docs/how-to`
- `dev/docs/sequences`

## Description

- Derive the fourteen affected sequence identifiers from the S18 commit instead of maintaining a parallel list.
- Run every affected sequence through the public bounded check with a 180-second supervisor deadline.
- Derive the five owning pages from those generated goldens and run every page through the public bounded coherence tier.
- Remove repeated quickstart ledger-add and evidence-attach code sites by making the shared seed own their runtime-derived captures.
- Regenerate only the four quickstart goldens whose canonical seed transcript changed.

## Outcome

All fourteen isolated sequence checks passed without a refresh. Four of the five owning pages passed immediately. The quickstart page then exposed genuine cumulative duplication: later sequences replayed the seed's idempotency key and attached evidence a second time. The shared seed now owns the expense and evidence captures once per page, and the export sequence no longer duplicates the later filing step. Its four affected goldens were regenerated through the owning CLI.

After remediation, all five page-coherence checks passed inside their 180-second bounds: `how-to/first-quarterly-filing`, `how-to/irpf-lifecycle`, `how-to/modelo-130`, `how-to/quickstart`, and `how-to/review-calculation-values`.

## Notes

No golden was edited by hand. The quickstart golden changes reflect the deliberate deletion of duplicate executed frames; product command output did not change.

