---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:8091d4a0099152a9028d9c0f628d8b6a2078f0fe5c68f2b71d0c635727a44441'
step_id: 'S362'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
