---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:f17b927a057684b3a7beb19215a515f5ac771683c167f71e69f5e88a8159d202'
step_id: 'S118'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Retire the copied fixture resolvers this campaign published unconsumed and cover the profile fixtures with their own tests

## Scope

- `dev/quality/unconsumed_export_ratchet.toml`

## Changes

- `M` `src/cadrumo/entrypoints/tui/devtools/profile_fixtures.py`
- `M` `src/cadrumo/entrypoints/tui/devtools/modelo_fixtures.py`
- `A` `src/cadrumo/entrypoints/tui/devtools/tests/test_profile_fixtures.py`
- `M` `dev/quality/unconsumed_export_ratchet.toml`
- `verify:` `uv run --no-sync python -m pytest src/cadrumo/entrypoints/tui/devtools/tests -n0` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.unconsumed_export_ratchet` -> `fail`

## Notes

Both fixture modules this campaign added published a `resolve_*` accessor copied
from the workbench registry they were modelled on. In the workbench module that
accessor has a real consumer; in these two it had none, and one of them had no
consumer at all because the profile module shipped with no test file. The
pattern was mirrored without checking whether the mirrored part was carrying
anything.

The modelo resolver is kept and unpublished rather than deleted: its own tests
exercise the refusal path for an unknown fixture id, so it is a module-internal
helper with real coverage, not dead weight. The profile one was deleted -- it had
no caller and no test.

The remaining unconsumed exports belong to a concurrent migration. The export
ratchet is left red on those.
