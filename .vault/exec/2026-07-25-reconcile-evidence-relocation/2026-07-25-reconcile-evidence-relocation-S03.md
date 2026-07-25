---
tags:
  - '#exec'
  - '#reconcile-evidence-relocation'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S03'
related:
  - "[[2026-07-25-reconcile-evidence-relocation-plan]]"
---

# Add the strict-frozen reconciliation record model carrying verdict and source kind and source reference and work unit id and the grounded diffs and advisories and instant and actor, reusing the existing strict-frozen diff and advisory models unchanged, with grounding stored rather than re-derived

## Scope

- `src/cadrumo/application/modelo/_reconcile.py`

## Description

- Add a strict-frozen record model carrying the bucket event id, bucket, work unit, source kind, source reference, verdict, grounded diffs, advisories, actor and instant.
- Reuse the existing strict-frozen diff and advisory models unchanged rather than restating their fields.
- Bind a repository over the registered namespace, reading its sensitivity, schema version and namespace off the definition rather than restating any of them.
- Store the evidence reference at full length, leaving the shortening to the bucket-event copy alone.

## Outcome

Grounding is stored, not re-derived, and the reason is recorded at the site rather than left to a reader to reconstruct. Re-deriving at read time would resolve the snapshot from modelo, filing year and period because revision resolution is law-determined, so a routine re-grounding sweep that moved a casilla's legal references without moving the revision id would silently rewrite the legal basis of a historical reconciliation, and one that did move the revision id would make the history unreadable.

The record reuses the two existing strict-frozen models unchanged, so a diff persisted here is the same typed object the report already carries.

Reads inherit the classification check and the inner-envelope version check from the shared bound repository. That version check is an equality against the namespace's declared version rather than a ceiling, which is what the governing decision requires.

## Notes

The equality-not-ceiling requirement is met by inheritance rather than by calling the newly landed inner-envelope predicate. The shared bound repository already compares the inner envelope version for equality and raises on any deviation, on both the single-record and the iterator read paths. Calling the predicate as well would have been a second gate on the same value at the same boundary; that predicate exists for hand-rolled read paths which do not inherit one.

The record model and its repository live beside the reconcile service rather than in a new module, matching the shipped IVA-wallet precedent, where the decision repository likewise lives in the application package that owns the concept.

Semantic discovery was unavailable for this work. The vaultspec-rag code index was truncated while reporting itself healthy, and three probes at 120, 300 and 600 second timeouts all expired with the service reporting itself degraded and one then three active index jobs. The service was not restarted. Every statement here rests on reading the owning packages and their exported surfaces directly, and on targeted pattern search against the current tree; a semantic miss would have proven nothing.

