---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:47b02857f696e1c3e3e82c5487e09062e9930f8c93e8abf045e650fdca03d58a'
step_id: 'S336'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the embedded Python child implementation from recovery-enrollment tests

## Scope

- `recovery enrollment integration tests`
- `direct platform invocation behavior`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `M` `dev/packaging/tests/test_recovery_enrollment.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q -n0 dev/packaging/tests/test_recovery_enrollment.py -m unit` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

Exact remeasurement reports the campaign's remaining live signal: 36 unreachable modules and 278 unused symbols. Four installed-command integration cases remain in their serial lane and were not selected by the focused unit command.
