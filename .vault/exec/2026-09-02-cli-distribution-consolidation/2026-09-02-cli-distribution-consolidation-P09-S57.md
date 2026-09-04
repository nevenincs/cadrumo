---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:509ba9170e98ba9285b5060bdfcd56386b727b99817513d8dfeda0f2b2570c2d'
step_id: 'S57'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

# Stop the clean-tree build root from carrying files git ignores and the wheel cannot

## Scope

- `dev/packaging/_smoke_common.py`

## Changes

- `M` `dev/packaging/_smoke_common.py`
- `M` `dev/packaging/tests/test_smoke_core_payload.py`

## Notes

The expectation was the defect, not the build root. The wheel is identical on
both branches -- the builder's file selection already honours version-control
ignore rules -- so only the expectation moved, which is why the refusal always
read as missing paths and never as surplus ones. A filesystem walk counted
ignored artifacts as payload the wheel must carry; every other inventory in the
pipeline already asks version control, and one consumer had been passing the
live repository as its build root unconditionally, so the sealed-extract
invariant the docstring asserted was never upheld anywhere.

The replacement tightens rather than relaxes the gate: under the old walk an
ignored artifact that genuinely leaked into a wheel was expected, and passed
silently. It now fails as surplus.

Repairing this reached a further defect that the earlier refusal had hidden by
aborting before the install: corpus annotations ship in a different
distribution from the binaries they annotate, so an installed split reads two
record designs as partial while the same validation passes from source. It is
tracked separately.

## Scope

- `dev/packaging/_smoke_common.py`

## Changes
