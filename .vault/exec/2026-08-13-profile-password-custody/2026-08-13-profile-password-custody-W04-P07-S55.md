---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:abea91343e225e1b33f051fcccf84a69e9f0fa25d1c6f127cac19c479b857996'
step_id: 'S55'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh measure the executed import graph across the storage adapter package and resolve the cycles that one hundred and seventy-four function-local deferred imports are currently concealing, since a deferred import postpones a cycle rather than removing it and the package proved it by raising a partially-initialised secret-store import the moment a routine edit changed evaluation order, then either break each real cycle at its architectural seam or declare it with the reason it cannot be broken, never by adding a further deferral

## Scope

- `src/cadrumo/adapters/persistence/storage/`

## Description

- Measure the executed import graph across the storage adapter package rather
  than the import-time graph, so cycles that deferral postpones are visible.
- Extract the runtime readiness projection into its own module so the cycle has
  an architectural seam to break at.
- Confirm the cycle is gone against the measured graph rather than by
  inspection.

## Outcome

The cycle the deferred imports were concealing was real, not hypothetical. The
package had already demonstrated it once by raising a partially-initialised
secret-store import the moment a routine edit changed evaluation order — a
deferred import postpones a cycle rather than removing it, and that failure is
what a postponement looks like when it finally lands.

The seam was between the storage runtime and the secure-objects SQL layer.
Extracting the readiness projection into `_runtime_readiness.py` breaks it at
the boundary rather than by adding a further deferral, which the Step forbids
and which would only have moved the failure again. The cycle was then confirmed
absent against the executed graph.

Storage lane after the change: 1282 passing, 1 failing, and the single failure
belongs to the concurrent registry authority-grade campaign rather than to this
package.

## Notes

Nothing was routed around a gate and no deferral was added. The 174
function-local deferred imports were the symptom under investigation, not a
target to be counted down: this row resolved the cycle they concealed, and the
remaining deferrals are not evidence of further concealed cycles by themselves.
