---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:af941babd701d9bfc31b53c3f5d1b8d41495b754181d7b2f91d9eb0c6f634c76'
step_id: 'S60'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# record separate asset-amortization and finca-amortization dispositions

## Scope

- `src/cadrumo/_data/source_connectivity/census.toml`

## Description

- Reconcile the asset-amortization and finca-amortization candidates against the accepted grounding and mapping decision.
- Preserve finca amortization as its separate bounded grounding refusal for casilla 0131.
- Replace the asset ledger's indefinite candidate state with an owned, expiring `ingress_blocked` disposition for the unimplemented validated 2025 activity-asset schedule.
- Point the follow-up at the actual taxonomy, selector, resolver, collision, provenance, encrypted-revision, replay, operator, and export work rather than repeating completed legal adjudication.

## Outcome

The two amortization domains now have separate truthful dispositions. Finca remains `grounding_blocked` under its own annual property contract. The asset amortization ledger is `ingress_blocked`: the accepted decision already settles exclusive 2025 schedule ownership for casillas 0208 and 0227 and collision refusal against transaction-ledger claims, but the typed governed source path and complete proof do not exist. Neither source is represented as connected.

The canonical comparison remains a 478-capability, 478-assignment match over 15 rows. The final focused census, permanent campaign-close, and source-coverage selection passed 9 tests; Ruff passed. Independent review rejected the initial `grounding_blocked` classification and stale adjudication follow-up, which were replaced before final re-review.

## Notes

No source kind, selector, resolver, binding, casilla, persistence channel, or export claim was added. S61 through S69 remain the implementation owners; S70 may promote only from complete live evidence.

The census change and initial tracking scaffolds were captured by concurrent mixed commit `47100882ca`. This record preserves that provenance rather than attributing the shared registry and CLI commit solely to S60; the corrected regression and final reviewed records are committed separately by exact path.
