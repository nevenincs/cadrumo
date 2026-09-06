---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:320f374c799f422da76dec614f2349a01ee5d26247b1956d59989de382bf70ba'
step_id: 'S66'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Make three cross-platform test legs assert their contract instead of the host that ran them

## Scope

- `dev/packaging/tests/test_smoke_scoop_harness.py`

## Changes

- `M` `dev/packaging/tests/test_smoke_scoop_harness.py`
- `M` `dev/packaging/tests/test_command_spec_source_lanes.py`
- `verify:` `pytest dev/packaging/tests/test_smoke_scoop_harness.py -n0 -m ''` -> `pass`
- `verify:` `pytest dev/packaging/tests/test_command_spec_source_lanes.py -n0 -m ''` -> `pass`
- `verify:` `ruff check` -> `pass`
- `verify:` `python -m dev.quality.types` -> `pass`

## Notes

Both files were absorbed into commit `9f0f673c41`, authored by a concurrent
session, whose message describes unrelated reachability work. The content is
correct and present in `HEAD`; history was not rewritten. The rationale is
recorded here because that commit message does not carry it.

Only two of the four macOS lane failures were macOS-specific. The completion
leg used `--show-completion`, which takes no shell argument and detects the
shell from the process tree, so it asserted whatever shell happened to be the
runner's parent; it was reproduced failing on Windows, and now renders for a
named shell through Click's public generator against the real command tree.

Two defects in `src/cadrumo/tests/_marker_hook.py` were found and left
untouched, that module belonging to another campaign: the serial holdout runs
before pytest's own `-m` deselection, so a lane invoked with `not serial` still
trips the hold and warns that tests it never selected did not execute; and
`record_held_from_node` and `fail_session_on_held_serials` are called from no
conftest, leaving the false-green they were written to close still open. Wiring
that enforcement before fixing the ordering would fail every correctly
configured lane. Both were relayed to the owning session.
