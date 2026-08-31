---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:91fa4a04890d48f9cde1ec277e5b7ab97d54bf049ed7c6c5991b8a822455ba6e'
step_id: 'S132'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Gate the identity algorithm and its policy tables to a single declaration, proved by mutation from outside the repository

## Scope

- `src/cadrumo/core/identity/tests/test_single_identity_algorithm.py`

## Changes

- `A` `src/cadrumo/core/identity/tests/test_single_identity_algorithm.py`
- `verify:` `pytest ... test_single_identity_algorithm.py -n 0 -m ""` -> `pass` (3)
- `verify:` mutation probe, run from the job scratch directory, reds all three arms

## Notes

Structural rather than a behavioural sample, because a sample cannot see a
validator that no test calls yet. Each policy table -- the two checksum tables,
the kind catalogue, and the digit-only and letter-only partitions -- must be
declared once, and the `% 23` and Luhn expressions must be computed only in the
pinned authority. Naming a table inside a docstring is allowed and distinguished
from re-declaring it as a value: prose documents the rule, a value implements it
a second time, and only the second drifts.

The third assertion is the anti-vacuity one. Without it, moving the tables out of
the authority makes the first two trivially true -- no module would restate a
table the gate can no longer find anywhere.

Proved by mutating the package from a script outside the repository so nothing
under `src` changed: a probe module restating `"ABEH"` reds the first arm, one
recomputing `% 23` reds the second, and rewriting the authority's own table as an
equivalent expression reds the third.
