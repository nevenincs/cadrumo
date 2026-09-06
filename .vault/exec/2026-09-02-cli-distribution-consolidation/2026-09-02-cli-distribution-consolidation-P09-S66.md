---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:4e2225c401c14b496fe3955d96f91b5bff16c08b23560037602138bf77d7d163'
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

Both files were absorbed into commit `9f0f673c41`, whose subject describes
unrelated reachability work. No contributor chose that: this worktree runs an
auto-committer, and every commit it makes stages the whole tree, so one subject
routinely spans files from several unrelated areas. The content is correct and
present in `HEAD`; history was not rewritten. The rationale is recorded here
because the commit message cannot carry it, and a commit subject in this
repository is not evidence of what that commit contains.

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
