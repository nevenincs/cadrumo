---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-05-calculation-truth-registry-phase2-step12-exec]]'
---



# `calculation-truth-registry` Code Review

PHASE2-STEP12-001 | HIGH | Justificante corpus contract still treated filenames as period authority

The wider justificante parser contract failed for annual fixtures after receipt
parsing stopped deriving `0A` from modelo identity. Resolved by updating the
contract to assert observed PDF output: explicit `0A` tokens remain `0A`, while
fixtures that print only the ejercicio now expect the ejercicio as the observed
receipt period.

PHASE2-STEP12-002 | MEDIUM | Year-only canonicalization was not registry-constrained

Import and reconciliation initially treated any receipt period equal to
ejercicio as annual. Resolved by exposing active registry period selector tokens
from the runtime subview and requiring `0A` support before year-only receipt
periods can canonicalize to annual draft periods.

PHASE2-STEP12-003 | MEDIUM | Reconciliation did not validate draft period support

Reconciliation checked active schema version but not whether the draft period
mapped to a period token declared by the active registry revision. Resolved by
requiring the draft period token to be present in the active subview before any
comparison is performed.

PHASE2-STEP12-004 | MEDIUM | Application behaviour coverage was incomplete

Resolved by adding behaviour coverage for justificante import rejecting
year-only receipts under a quarterly registry revision, reconciliation reporting
year-only remote periods as mismatches for quarterly drafts, and reconciliation
rejecting drafts whose period is not declared by the active registry snapshot.
