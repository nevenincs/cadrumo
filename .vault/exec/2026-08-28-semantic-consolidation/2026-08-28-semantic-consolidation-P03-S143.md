---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:9759fcc747e638477a9700534ffa103f18e0ebc4789284bd8cb3b2a65649277a'
step_id: 'S143'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Gate every shipped holiday calendar on actually loading, discovering the years from disk rather than naming them, and prove it by restoring the defect that shipped

## Scope

- `src/cadrumo/core/resources/_repos/tests/test_every_shipped_resource_loads.py`

## Changes

- `A` `src/cadrumo/core/resources/_repos/tests/test_every_shipped_resource_loads.py`
- `verify:` `pytest .../test_every_shipped_resource_loads.py -n 0 -m ""` -> pass (3)
- `verify:` mutation probe from the job scratch directory: green as shipped, RED with the
  coercing boundary made strict again, green after restoring

## Notes

The festivos calendars shipped unloadable. The sibling tests in this package DO
load calendars and were red, so the failure was not invisible -- but they name
their years as literals, `get(2024)` and `get(2025)`. A data family grows by
having a file added to it, and a test that names the years it knows about cannot
notice the one that arrives next: `festivos-2026.toml` shipped covered by
nothing.

So this gate DISCOVERS the years from disk. It is over the property "every file
we ship can be read by the loader that owns it", not over a count or a list, and
it gets stronger on its own each time a file is added. It catches a bare
`Exception` deliberately: narrowing to the errors one expects would reintroduce
the blind spot, since the original failure was a pydantic ValidationError nobody
predicts a TOML loader will raise.

Three assertions, and the first two matter together: an anti-vacuity check that
the discovery found any files at all, the load check, and a content check that a
loaded calendar declares holidays -- because a calendar that parses to nothing
shifts nothing, which is indistinguishable from the failure that prompted this.

### Proving it took three corrections, each of which looked like proof

The mutation probe restores the exact shipped defect from outside the repository.
Getting there was instructive and the reasons are recorded in the probe:

Reassigning `model_config` on a built model is inert -- pydantic compiles the
core schema at class creation -- so the rows have to be subclassed.

Subclassing the rows is not enough either: the outer document model's field
annotations still name the ORIGINAL row classes, so its rows keep validating
leniently. The outer model has to be rebuilt against the strict rows.

And `load_holiday_calendar` carries an `lru_cache` on top of the repository's
own identity map, so clearing one cache and not the other serves the mutation a
result parsed before it.

The last one is the one worth carrying forward. The probe ran pytest in-process
and pytest defaults to xdist here, so the gate executed in FRESH WORKER PROCESSES
that never saw the in-memory mutation. Three runs came back green and read
exactly like a blind gate. An in-process mutation probe MUST pass `-n 0`, or it
measures nothing and says so in the same words a passing gate uses.
