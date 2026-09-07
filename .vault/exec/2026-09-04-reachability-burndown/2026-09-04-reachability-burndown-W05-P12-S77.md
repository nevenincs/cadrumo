---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:5788341c6cab62b828344af37ef73b380a961cd99f4da2f112e79bf425930390'
step_id: 'S77'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Gate the defect class the previous step fixed by hand: no shipped call to the approval or staleness entry points may pass a basis override, since the recomputation that decides whether an approval aged out self-loads every axis from the bucket and an override supplied at approval time and absent at refresh time makes that axis disagree by construction. Passing the keyword at all is the offence, None included. Prove the teeth against the live tree by reintroducing the exact call the workflow gate used.

## Scope

- `src/cadrumo/application/filing/tests/test_approval_basis_is_bucket_derived.py`

## Changes

- `A` `src/cadrumo/application/filing/tests/test_approval_basis_is_bucket_derived.py`
- `verify:` `pytest .../test_approval_basis_is_bucket_derived.py` 8 passed
- `verify:` teeth proved against the LIVE tree -- restoring the workflow gate's
  `approve_draft(transaction_catalogue=...)` turns the gate red naming
  `workflow_gate.py:235`; restored and re-verified green
- `verify:` `ruff check` and `ty check` clean

## Notes

The invariant belongs to the PAIR, not to either function, which is why nothing
caught the original defect: approval and refresh were each internally correct
and only their exchanged digest was wrong. Stating it as a rule over call sites
is what makes it checkable before a draft is ever stored.

`=None` is an offence too. Spelling an override out says the caller believes it
controls that axis, and the value a caller passes today is the one it stops
passing tomorrow; the honest way to self-load is to omit the argument. The teeth
case uses exactly that harmless-looking form and the gate still fires.

The module lives under `src/cadrumo/` rather than `dev/quality/` on purpose: the
default pytest `testpaths` covers `src/cadrumo`, so it runs in the normal lane
without any enrolment step, unlike the secure-store gate added earlier which
needed both a `just` recipe and a lane assertion before it could fail CI.

`draft_review.py` is skipped by the scan. It declares the override parameters and
forwards them between its own functions, so it is the boundary the rule protects
rather than a caller that can violate it.
