---
tags:
  - '#exec'
  - '#reconcile-evidence-relocation'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S02'
related:
  - "[[2026-07-25-reconcile-evidence-relocation-plan]]"
---

# Design the object key to admit N reconciliations per work unit rather than overwriting, and to admit the runs that carry no persisted revision at all, since receipt-total and declaracion-casilla reconciles emit a no_persisted_revision advisory and still produce a report and identity-header reconcile needs no revision

## Scope

- `src/cadrumo/application/modelo/_reconcile.py`

## Description

- Key the record as the literal reconciliation prefix, then the work unit id, then the bucket event id.
- Derive the trailing segment from the content-addressed id of the bucket event co-written with the record, rather than from a clock, a counter or a revision.
- Validate both components through the shared repository-id contract before composition.
- Record on the key function why each of the two properties holds.

## Outcome

Both properties the key exists for hold, and both are gated rather than reviewed.

N per work unit: the event id already folds the reconciliation instant, the actor, the verdict and the divergence count, so every distinct run keys distinctly, while a byte-identical re-emission collapses exactly as the append-only event log itself collapses it. This also joins the record to its event by identity, so neither side needs a cross-reference field that could drift.

No revision required: nothing in the key derives from a calculation revision. The receipt-total and declaracion-casilla reconciles both emit a no-persisted-revision advisory and still produce a report, and an identity-header reconcile needs no revision at all. A revision-derived key could not have stored those runs, which was one of the three independent reasons the bundle-into-the-revision option was rejected.

The N-per-work-unit property was proven to be a real gate rather than an assertion: collapsing the key to the work unit alone was applied to the production module as a temporary probe, and both key tests went red as intended before the authored file was restored.

## Notes

A work unit id and an event id are both sixty-four character digests, so the composed key is about one hundred and forty characters and comfortably inside the storage id contract.

Semantic discovery was unavailable for this work. The vaultspec-rag code index was truncated while reporting itself healthy, and three probes at 120, 300 and 600 second timeouts all expired with the service reporting itself degraded and one then three active index jobs. The service was not restarted. Every statement here rests on reading the owning packages and their exported surfaces directly, and on targeted pattern search against the current tree; a semantic miss would have proven nothing.
