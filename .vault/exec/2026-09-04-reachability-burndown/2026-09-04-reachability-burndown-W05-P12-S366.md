---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:c78296d79545417fbeb701ebf19c3f756cd04d48dc6653fe46c313ffb7798b07'
step_id: 'S366'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Remove the unwired donativo export resolver and private builder together with their builder-only test and the hand-maintained row-field completeness detector.

## Scope

- `donativo registry bindings`
- `application row assembly prose`
- `detail-record tests`
- `exact unused-symbol signal`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/donativo_bindings.py`
- `M` `src/cadrumo/application/calculations/row_set_assembly.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_detail_record_observations.py`
- `D` `src/cadrumo/domain/calculations/registry/tests/test_detail_row_field_declaration_coverage.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/donativo_bindings.py src/cadrumo/domain/calculations/registry/tests/test_detail_record_observations.py src/cadrumo/application/calculations/row_set_assembly.py` -> `pass`
- `verify:` `uv run --no-sync pytest -n0 -m "" src/cadrumo/domain/calculations/registry/tests/test_detail_record_observations.py src/cadrumo/application/calculations/tests/test_row_set_assembly.py -q` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`
