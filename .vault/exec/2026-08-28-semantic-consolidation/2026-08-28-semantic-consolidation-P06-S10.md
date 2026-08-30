---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-29'
modified: '2026-08-29'
body_schema: 'body-v2'
body_hash: 'sha256:a98b52a343ca13651c54abe3547b3922f694573b850fbaa3f2e08a7fa23e4814'
step_id: 'S10'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Declare the filing-year window once in core and record why the floor is the registry's first authored revision

## Scope

- `src/cadrumo/core/filing_year.py`

## Changes

- `A` `src/cadrumo/core/filing_year.py`
- `M` `src/cadrumo/core/_period.py`
- `M` `src/cadrumo/domain/calculations/registry/schema_scalars.py`
- `M` `src/cadrumo/domain/calculations/registry/query_reports.py`
- `M` `src/cadrumo/application/modelo/_export.py`
- `M` `src/cadrumo/application/modelo/_review_package.py`
- `M` `src/cadrumo/application/modelo/_edit_models.py`
- `M` `src/cadrumo/application/modelo/operation_definitions.py`
- `M` `src/cadrumo/application/modelo/workspace_models.py`
- `M` `src/cadrumo/application/export/google_operation.py`
- `M` `src/cadrumo/application/registry/source_connectivity.py`
- `M` `src/cadrumo/application/overview/_explain.py`
- `M` `src/cadrumo/application/state_projection.py`
- `M` `src/cadrumo/application/user_profile/commands.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_aux_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_review_package_payloads.py`
