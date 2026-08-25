---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:1b6af8e94e9b21d1b59acf32e7844aaf48415ee4be231feea1057351049b38ad'
step_id: 'S54'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# promote inventory to connected only when a grounded row-capable format and every connected proof pass, otherwise record the evidence-backed blocked disposition with an owned follow-up

## Scope

- `src/cadrumo/_data/source_connectivity/census.toml`

## Description

- Reconcile the inventory candidate against the accepted row-casilla mapping decision and the live resolver, mesh, bindings, and persistence path.
- Refuse promotion to connected because registry-owned row-casilla materialization and supported official activity-row rendering remain absent.
- Replace the indefinite candidate state with an owned, expiring `registry_blocked` disposition and preserve the existing bounded follow-up.
- Update the census and closure-composer regressions to pin the terminal blocked classification and visible missing-evidence refusal.

## Outcome

Inventory is not represented as connected. Its legal three-casilla semantics, source resolver, governed ingress, registry row bindings, encrypted source state, and calculation orchestration remain acknowledged, while filing linkage is terminally `registry_blocked` through 2026-12-31. Reopening requires the already accepted row-casilla materialization and official-format proof without fabricated activity-envelope facts.

The canonical census comparison remains a 478-capability, 478-assignment match over 15 rows. The focused composer suite passed 7 tests; census completeness plus the permanent campaign-close gate passed 22 tests; Ruff passed. Independent review rejected one stale expected refusal reason, which was corrected before final re-review.

## Notes

The initial census, test, and scaffold changes were captured by concurrent mixed commit `718caf5911`. This record preserves that provenance rather than attributing the shared commit solely to S54. No registry binding, source resolver, source taxonomy, casilla, export layout, or proof authority was added.
