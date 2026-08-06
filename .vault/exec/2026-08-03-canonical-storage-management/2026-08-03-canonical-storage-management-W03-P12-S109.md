---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:8bd7e76c705635955fe7e1a07130960ceec3a454c6520aaaad4dd4decd652a22'
step_id: 'S109'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Fix the stale expected tuples in the compatibility-lifecycle gate's enrollment-predicate test, campaign-caused by this campaign's own persisted-format declarations adding bucket_database_file and secret_index, currently red at HEAD across all three parametrised cases, routed

## Scope

- `consider deriving the expectation from the declared formats rather than restating it by hand`
- `since a hardcoded census of uncovered formats is the gate shape this project forbids elsewhere`
- `src/cadrumo/tests/test_compatibility_lifecycle_gate.py`

## Description

- Confirm `bucket_database_file` is genuinely declared `DURABLE` in the
  persisted-format inventory, grounded in its own documented rationale (the
  per-bucket SQLite file carrying the encrypted `secure_object` rows -- real
  taxpayer data at the container level, no rebuild path).
- Update the three parametrised `floors` -> `expected` tuples in the
  enrollment-predicate test to include `bucket_database_file` in its correct
  sorted position, and correct the accompanying "two durable formats" comment
  to "three".
- Deliberately did NOT derive the expected tuples from the declared format
  set programmatically, despite the Step row's suggestion to consider it.

## Outcome

Fixed all three parametrised cases (`floors0/1/2`), previously red at HEAD.
The test's own docstring states its purpose is non-vacuity: proving the
predicate under test is not "always return an empty tuple". Deriving the
expected value by re-computing the same filter the predicate itself applies
(durable-and-not-in-floors) would make the test tautological -- it would
verify only that the predicate agrees with itself, exactly the failure mode
the test exists to rule out. The hand-typed literal tuples are the
independent oracle; the fix updates that oracle's one stale entry rather than
routing around the discipline that makes it a real check.

## Notes

None. No skipped work, no scaffolds left in code.
