---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:b96b3fd427f54576974a68a701c453e92dbf81873635ccaee4d39865b0cc27dc'
step_id: 'S50'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Define frozen callback-free Workspace chrome, destination, section, scalar, repeated-row, provenance, capability, refusal, validation, and action view models keyed only by semantic identity

## Scope

- `src/cadrumo/entrypoints/tui/modelo/view/models.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/modelo/view/models.py`
- `A` `src/cadrumo/entrypoints/tui/modelo/view/tests/test_workspace_view_models.py`
- `A` `src/cadrumo/entrypoints/tui/modelo/view/tests/conftest.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/modelo/ -m "unit or integration" -n0 -q` -> `pass` (112 passed; the 2 failures are in `src/cadrumo/entrypoints/tui/modelo/view/tests/test_work_review.py`, peer-held and outside this Step)
