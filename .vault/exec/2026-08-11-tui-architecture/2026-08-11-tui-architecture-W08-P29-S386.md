---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:7f934b314eb45b53f2d06daa363c5a32a6f61b29fc4b339ab6916e2587ac213d'
step_id: 'S386'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Prove Home and every principal workspace preserve content, navigation, focus, and single-scroll ownership across supported sizes, themes, and locales

## Scope

- `src/cadrumo/entrypoints/tui/tests/test_workbench_responsive.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/tests/test_workbench_responsive.py`
- `A` `src/cadrumo/entrypoints/tui/tests/workbench_session.py`
- `verify:` `uv run --no-sync pytest -q -m integration src/cadrumo/entrypoints/tui/tests/test_workbench_responsive.py` -> `pass`
