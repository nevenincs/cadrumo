---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:0e90436881ed18fac733b45817953565d1433187460ad75d7f2dcf4345ccbba0'
step_id: 'S406'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Make the coverage table agree with the surfaces the harness can actually drive. The fixture registry is now the authority for review surfaces and the harness lists 60 of them, up from 6, but `python -m dev.tui inventory` still reports '60 interfaces, 52 not rendered' because it reads a coverage map that predates that wiring. An inventory that under-reports coverage is the same defect as one that over-reports it: either way the missing-surface gate cannot be read, which is how 52 surfaces sat unrendered without anyone noticing.

## Scope

- `dev/tui/_coverage.py and dev/tui/_inventory.py`

## Changes

- `M` `src/cadrumo/entrypoints/tui/devtools/surfaces.py`
- `M` `src/cadrumo/entrypoints/tui/devtools/__main__.py`
- `M` `dev/tui/_harness.py`
- `M` `dev/tui/_coverage.py`
- `M` `dev/tui/cli.py`
- `verify:` `uv run --no-sync python -m dev.tui inventory` -> `pass`
- `verify:` `uv run --no-sync pytest -q dev/tui/tests` -> `pass`
