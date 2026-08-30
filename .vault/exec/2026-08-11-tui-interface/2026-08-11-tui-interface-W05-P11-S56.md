---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:0b594d9d01c008cf2a158166d5adf830439f230ee0c9cf98f11042f234923a31'
step_id: 'S56'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Render modelo.workspace.verification from canonical findings, readiness axes, capability dispositions, evidence, and recovery actions without deriving a second readiness verdict

## Scope

- `src/cadrumo/entrypoints/tui/modelo/view/verification.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/modelo/view/verification.py`
- `A` `src/cadrumo/entrypoints/tui/modelo/view/tests/test_workspace_verification.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/modelo/ -m "unit or integration" -n0 -q` -> `pass` (112 passed; the 2 failures are in `src/cadrumo/entrypoints/tui/modelo/view/tests/test_work_review.py`, peer-held and outside this Step)
