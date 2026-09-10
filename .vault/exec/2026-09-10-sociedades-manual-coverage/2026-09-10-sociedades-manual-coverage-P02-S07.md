---
tags:
  - '#exec'
  - '#sociedades-manual-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:ec294229eed44c3e70b91d82eb4ba88bb09736723e5d0b1cff9078c4708f1ae2'
step_id: 'S07'
related:
  - "[[2026-09-10-sociedades-manual-coverage-plan]]"
---
# Narrow Modelo 200 family evidence references so annual manuals never ground an out-of-window year

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/200/revisions`

## Changes

- `M` `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024`
- `M` `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2025-y-siguientes`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_200_registry.py`
- `verify:` `uv run pytest src/cadrumo/domain/calculations/registry/tests/test_modelo_200_registry.py::test_modelo_200_revision_fragments_never_cite_another_years_annual_manual src/cadrumo/domain/calculations/registry/tests/test_modelo_200_registry.py::test_modelo_200_validates_with_deadline_and_schedule_catalogue_refs -q` -> `pass`
