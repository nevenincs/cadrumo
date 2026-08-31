---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:c2dbe4656dbc856bbcc847dc7ce9db1a2b7514b97709dfdb5783b0a9fc9407b4'
step_id: 'S187'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# `ci-lane-deconflation` execution record: `P05.S187`

## Scope

- `P05.S187`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/invoice_bindings.py`
- `A` `src/cadrumo/domain/calculations/registry/_invoice_row_materialization.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_349_operador_totals_parity.py`
- `M` `.vault/plan/2026-08-05-ci-lane-deconflation-plan.md`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S187.md`

## Notes

- `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/invoice_bindings.py src/cadrumo/domain/calculations/registry/_invoice_row_materialization.py src/cadrumo/domain/calculations/registry/tests/test_modelo_349_operador_totals_parity.py` emitted `All checks passed!` (exit 0); `uv run --no-sync ruff format --check src/cadrumo/domain/calculations/registry/invoice_bindings.py src/cadrumo/domain/calculations/registry/_invoice_row_materialization.py src/cadrumo/domain/calculations/registry/tests/test_modelo_349_operador_totals_parity.py` emitted `3 files already formatted` (exit 0); `git diff --check` exited 0.
- `uv run --no-sync pytest -o addopts='' --collect-only -q -m unit src/cadrumo/domain/calculations/registry/tests/test_invoice_bindings.py src/cadrumo/domain/calculations/registry/tests/test_modelo_347_registry_bindings.py src/cadrumo/domain/calculations/registry/tests/test_modelo_349_registry_bindings.py src/cadrumo/domain/calculations/registry/tests/test_modelo_349_operador_totals_parity.py src/cadrumo/domain/calculations/registry/tests/test_modelo_347_contraparte_clave_bindings.py src/cadrumo/domain/calculations/registry/tests/test_contraparte_clave_row_grouping.py` collected 49 tests (exit 0); the matching focused run emitted `49 passed in 16.52s` (exit 0).
- `uv run --no-sync python -c "from dev.audit.size_budget import measure_module_lines; actual=measure_module_lines(); key='src/cadrumo/domain/calculations/registry/invoice_bindings.py'; print(f'{key}: {actual[key]} lines; default module budget 1250; exit 0')"` emitted `src/cadrumo/domain/calculations/registry/invoice_bindings.py: 894 lines; default module budget 1250; exit 0`; no policy or baseline changed.
- Before S187 plan mutation, `HEAD` was `caa2f71a28a38add5b9006cb4a2e08e729376b2e` and the shared default-index/worktree plan blob was `6f53b32289f080715f2ace1a5cfc60692c4872bb`; the isolated commit stages only the S187 row and generated body hash while preserving peer plan hunks byte-identically.
