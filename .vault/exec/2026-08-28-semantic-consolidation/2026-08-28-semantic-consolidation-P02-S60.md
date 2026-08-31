---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:16aff45df6d19f0a947b96e7617cd71af16343655c39851916bfe8f59b481e33'
step_id: 'S60'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Reconcile the actor concept, declared at sixty-four on the filing label and a hundred and twenty-eight on the review package while both are fed by the same operator resolver

## Scope

- `src/cadrumo/`

## Changes

- `M` `src/cadrumo/domain/modelos/filing_text.py`
- `M` `src/cadrumo/application/modelo/review_package.py`
- `verify:` both aliases probed at 1, 64, 128, 129 -- identical, refusing only above 128
- `verify:` `pytest domain/modelos + application/modelo -k "filing_text or actor or review_package or reconciliation" -n 0 -m ""` -> 152 pass, 1 unrelated

## Notes

The two actor bounds were 64 on the filing label and 128 on the review package,
fed by one operator resolver. The review package's own docstring had already
recorded the difference as "unexplained rather than principled" and declined to
narrow it, on the grounds that tightening a persisted bound is a decision about
stored data rather than a de-duplication. That reasoning was right and this
reconciles the other way instead.

Widening refuses nothing that was accepted before, so the only question was
whether the 64 was load-bearing. It was not: no fixed-width export slot binds an
actor, checked across the registry export records, so nothing downstream relied
on it. Both aliases now read one `ACTOR_LABEL_MAX_LENGTH`.

Both names stay. A review-package actor and a filing actor are different roles
that happen to share a shape, and collapsing the names would lose that; what had
to stop differing is the number.

The one failing test in the area asserts a `MISSING_REQUIRED_CASILLA` finding on
an M190 verification, with `verified_by='test-operator'` at thirteen characters
-- unrelated to any bound this step touched.
