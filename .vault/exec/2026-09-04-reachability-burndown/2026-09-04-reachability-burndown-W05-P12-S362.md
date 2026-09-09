---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:807b0e056a2688b38dc010237c1816004793c92027f8759b1cd2d7824363d91c'
step_id: 'S362'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete five unapplied or superseded legal constants and correct maternity documentation to name the dated registry as its sole authority.

## Scope

- `core external constants`
- `maternity domain documentation and owner tests`
- `exact unused-symbol signal`

## Changes

- `M` `src/cadrumo/core/external_constants.py`
- `M` `src/cadrumo/domain/contribuyente/deduccion_maternidad.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -n0 -m "" src/cadrumo/domain/contribuyente/tests/test_deduccion_maternidad_0611.py src/cadrumo/core/tests/test_external_constants.py -q` -> `pass (78 passed)`
- `verify:` `uv run --no-sync ruff check src/cadrumo/core/external_constants.py src/cadrumo/domain/contribuyente/deduccion_maternidad.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass (235 unused symbols; down from 240)`
