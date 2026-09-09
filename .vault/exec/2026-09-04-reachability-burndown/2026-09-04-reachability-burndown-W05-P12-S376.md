---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:1db784f722fccdd3565656966e468abb6228e020814b657b1af642f111785cbd'
step_id: 'S376'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---
# Resolve the remaining exact unreachable symbols in application and core ownership without compatibility surfaces.

## Scope

- `src/cadrumo/application`
- `src/cadrumo/core`

## Changes

- `D` `src/cadrumo/application/filing/_export_proof_contracts.py`
- `D` `src/cadrumo/application/filing/export_proof.py`
- `D` `src/cadrumo/application/registry/closure_capture.py`
- `D` `src/cadrumo/application/registry/filing_export_coverage.py`
- `M` `src/cadrumo/application/modelo/calculation.py`
- `D` `src/cadrumo/application/modelo/tests/test_calculation_capture.py`
- `M` `src/cadrumo/application/modelo/work_review.py`
- `M` `src/cadrumo/application/state_projection.py`
- `M` `src/cadrumo/core/errors/registry/_application_part2.py`
- `M` `src/cadrumo/locales/en/errors.yml`
- `M` `src/cadrumo/locales/es/errors.yml`
- `M` `src/cadrumo/locales/ca/errors.yml`
- `M` `src/cadrumo/locales/hu/errors.yml`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact --full` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/modelo/calculation.py src/cadrumo/application/modelo/work_review.py src/cadrumo/application/state_projection.py src/cadrumo/core/errors/registry/_application_part2.py` -> `pass`
