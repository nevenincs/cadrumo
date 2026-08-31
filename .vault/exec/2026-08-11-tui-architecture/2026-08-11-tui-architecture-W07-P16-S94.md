---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:3604e80e9b3cf3c45cd20e7deca8d03757e5da27ff75dce457d617310d88799f'
step_id: 'S94'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Request cancellation at every declared cancellable phase and prove acknowledgement, cleanup completion, lock release, and child-process reaping

## Scope

- `src/cadrumo/application/operations/tests/test_cancellation_cleanup.py`

## Changes

- `A` `src/cadrumo/application/operations/tests/test_cancellation_cleanup.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/operations/tests/test_cancellation_cleanup.py -m integration -n0 -q` -> `pass`

## Notes

Discovery for this Step ran against the local fallback search index, not the live
semantic-search service, which was down for the session. Absence of a result in that
index is therefore not evidence that no such code exists; every claim about what does
or does not exist in the tree was confirmed by direct search of the source rather than
by the index alone.

The operation definition and executor are declared by the test; the supervisor, its
cancellation and cleanup machinery, and the persistence adapters are production. No
shipped definition declares the owned-process resource family at all, let alone
combined with cooperative cancellation, so this proves the supervisor honours the
contract rather than that a shipped operation exercises it.

The cancellation request is injected by the test, which is what a cancellation proof
requires. The exactly-once close is proven against the supervisor's own release path
and not a harness release: neutering that method leaves the child unclosed and
unreaped.
