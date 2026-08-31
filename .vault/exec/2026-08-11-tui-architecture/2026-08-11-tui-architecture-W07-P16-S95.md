---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:5f3f2f1bb752880167ac5c59679a0876460c60e5d6219cdb25b3c1e260b2e7d9'
step_id: 'S95'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Enforce aggregate and cleanup deadlines without publishing timed out while execution or owned resources continue

## Scope

- `src/cadrumo/application/operations/tests/test_deadline_settlement.py`

## Changes

- `A` `src/cadrumo/application/operations/tests/test_deadline_settlement.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/operations/tests/test_deadline_settlement.py -m integration -n0 -q` -> `pass`

## Notes

Discovery for this Step ran against the local fallback search index, not the live
semantic-search service, which was down for the session. Absence of a result in that
index is therefore not evidence that no such code exists; every claim about what does
or does not exist in the tree was confirmed by direct search of the source rather than
by the index alone.

The definition and executor are test-declared; the deadline arithmetic, cancellation
request, cleanup enforcement, escalation and settlement guards are production, and the
negative invariant is read from the durable journal on disk rather than from
supervisor memory.

Two constraints on any future test in this area, both found by building the wrong
thing first. A frozen or advanceable clock cannot drive these paths: the supervisor's
waits are real awaits with real timeouts, so a frozen clock never expires them and the
case hangs. What the test controls is the release of the live thing, not the clock.
And a deadline window short enough to expire before the guarded work begins exercises
a different supervisor path than intended: a few-millisecond aggregate window can
expire before the executor has even entered, and a cleanup window can expire before
settlement has begun the close. Both windows are therefore wide enough that they
cannot lose that race, while the live thing is held open so they still expire
underneath it.
