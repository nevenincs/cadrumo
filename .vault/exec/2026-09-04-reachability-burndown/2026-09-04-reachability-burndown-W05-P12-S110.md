---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:f1414ef6b9b563c22a430a980334abd981214ac8d69528d69916a963bd111f97'
step_id: 'S110'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Classify the five remaining open unreachable TUI modules: the operations door, the retained Home candidates, and the staged error/log presentation trio

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `M` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S109.md`
- `verify:` `uv run --no-sync python -m pytest dev/audit/tests -n0` -> `pass`

## Notes

`cadrumo.entrypoints.tui.operations.facade` was a deletion candidate on the
numbers -- no importers, no callers, not even a test -- and would have been the
wrong call. Three docstrings name it, one of them in a file belonging to a
concurrent migration that states presentation is `present_operation_modal`'s job
and returns a controller for a caller to hand to it. The module is an unwired
door in someone else's in-flight design, so it is classified, not removed.
