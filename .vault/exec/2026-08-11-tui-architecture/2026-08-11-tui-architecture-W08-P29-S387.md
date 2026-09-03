---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:4aa671e279553ba20d35140f09e21f0c516eff9c082ffe62005ca687fe89c530'
step_id: 'S387'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Prove keyboard-only navigation, semantic focus restoration, non-colour state pairs, contextual help, and command-palette parity

## Scope

- `src/cadrumo/entrypoints/tui/tests/test_workbench_accessibility.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/tests/test_workbench_accessibility.py`
- `M` `src/cadrumo/entrypoints/tui/home.py`
- `verify:` `uv run --no-sync pytest -q -m integration src/cadrumo/entrypoints/tui/tests/test_workbench_accessibility.py` -> `pass`
