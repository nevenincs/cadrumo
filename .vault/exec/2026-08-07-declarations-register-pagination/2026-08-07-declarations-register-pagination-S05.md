---
tags:
  - '#exec'
  - '#declarations-register-pagination'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:d2127ba5fcc0cc0ac8ac731024f1cf391dc4a081008d5482f36aac3c01192ae0'
step_id: 'S05'
related:
  - "[[2026-08-07-declarations-register-pagination-plan]]"
---
## Description

A gate is unproven until it has failed on demand. The refusal test was broken
deliberately, three different ways, and confirmed to red each time.

## Outcome

No tracked file was edited to perform the proof. Each mutation is a pytest
plugin living outside the repository, loaded for one run with `-p`, so nothing
under `src` changed at any point and a peer's tree-wide commit could not sweep
the mutation in. The tracked tree was confirmed to carry no dirty file from
this change afterwards.

## Verification

Ordered run, one test module, same command each time:

- Clean baseline: 3 passed.
- Mutation resident, `truncated` forced to `False`: 2 failed, 1 passed. The
  refusal test reports `DID NOT RAISE SedeParseError`; the page-reporting test
  reports the page carrying `declared_total=8` with `truncated` false against
  fewer rendered rows, which is exactly the rendered-versus-declared mismatch
  going undetected.
- Mutation removed: 3 passed.

Two further mutations were run against the same module. Forcing the pager total
to never be read reds the same two tests. Forcing `truncated` to `True` reds the
no-pager non-regression test instead, refusing the real single-row capture. Both
directions of detector error therefore fail on demand: one that never fires and
one that fires on everything. A fourth mutation, tightening the failure row's
message bound, reds the taxonomy test recorded under S03.

The pass condition is the property, not the numbers. Both the declared total and
the rendered row count are read independently out of the raw fixture markup, so
a regenerated fixture of a different size travels with the assertions.

## Notes

No live AEAT probe was involved in any part of this proof.
