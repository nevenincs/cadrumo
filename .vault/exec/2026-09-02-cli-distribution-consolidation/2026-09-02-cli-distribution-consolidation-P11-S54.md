---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:28ac13e68dd9766a6c1c2fff91eb2bcb2861cc1dd152a74de288da5ed3d30632'
step_id: 'S54'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

# Cover the test directory reachable only by naming one file, and discover the class

## Scope

- `justfile`

## Changes

- `M` `justfile`
- `M` `dev/ci/lane_reachability.py`
- `M` `dev/tests/test_lane_reachability.py`
- `M` `dev/ci/tests/test_machine_aware_load.py`

## Notes

The new directory-level gate is RED against the tree, and deliberately so. It
reports five test directories no lane sweeps: the container, registry
conformance, registry parity, smoke and TUI packages. All five were added the
same day by other campaigns, several carry failing tests of their own, and the
pre-existing file-level gate already reports the same five. Wiring them into a
lane here would import another contributor's failures into a lane this change
owns, so the finding is left visible and unclaimed rather than silenced or
absorbed.

The class was larger than the Step assumed. Seven directories qualified, and
the one the Step named was not among those the file-level gate could see: its
single module IS named by a recipe, so every file-level question passed while a
second module added beside it would have run nowhere. That asymmetry is the
reason the directory question needed asking.

## Scope

- `justfile`

## Changes
