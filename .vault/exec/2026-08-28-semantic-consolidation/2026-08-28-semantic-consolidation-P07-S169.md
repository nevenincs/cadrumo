---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:70448ac6397a3b1c2421874033b243d9de863b46fd752a3ca61756340747a8ef'
step_id: 'S169'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Correct the restored packaging oracle that asserts the retired cadrumo.entrypoints.cli:main console script instead of the live _cli_main:main, once a built wheel is available to verify against

## Scope

- `dev/packaging/tests/test_installed_oracles.py`

## Changes

- `M` `dev/packaging/tests/test_installed_oracles.py`
- `verify:` built the wheel and read its `entry_points.txt`: `aeat = cadrumo.entrypoints._cli_main:main`

## Notes

The oracle asserted the console script is `cadrumo.entrypoints.cli:main`.
`pyproject.toml` declares `cadrumo.entrypoints._cli_main:main`, and the built
wheel agrees with `pyproject.toml`.

`_cli_main.main` defers logging configuration and then calls `cli.main`, so both
names exist and both are callable. That is why the drift was invisible: reading
either file alone shows a working entry point, and only the packaging metadata
distinguishes which one ships.

The two sides were dated to settle the direction rather than guess it. The
`pyproject.toml` change landed at 15:20; the assertion arrived at 19:04 the same
day in a commit named `restore: recover harness deployment verification`. So the
assertion is older content reinstated over a newer surface -- the documented
pattern of the restored harness lagging what it couples to, not a deliberate
pin.

### It was recorded as unverifiable, and that was wrong

This was first written up as needing a built wheel that was not available, and
tracked for someone else. That was an assumption, not a finding: `uv build
--wheel` succeeds here in under a minute, and reading `entry_points.txt` out of
the resulting archive settles the question directly.

The reasoning had been sound enough to act on -- pyproject is the source of
truth, and the commit ordering confirmed the direction -- but it stayed
inference until the artefact was read. The correction is cheap and worth
stating: before declaring something unverifiable, try the verification.
