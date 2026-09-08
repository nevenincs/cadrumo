---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:bba72ec6d4daef43de9cc6ec8adc14729c3ca44490626d57f296cac618817913'
step_id: 'S226'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Withdraw the wholly unreachable contabilidad prototype package, its three dormant error registrations, and all four synthetic model suites; preserve the accepted Modelo 200 base-determination chain at the live registry/calculation owner, which neither names nor consumes these speculative PGC, correction, direction, or trial-balance representations.

## Scope

- `Contabilidad domain prototype and tests`
- `central error registry`
- `accepted Modelo 200 base-determination decision and live calculation ownership`
- `exact reachability signal`
- `focused gates`
- `cadence reference`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `src/cadrumo/core/errors/registry/_application_part2.py`
- `D` `src/cadrumo/domain/contabilidad/__init__.py`
- `D` `src/cadrumo/domain/contabilidad/ajuste.py`
- `D` `src/cadrumo/domain/contabilidad/cuenta.py`
- `D` `src/cadrumo/domain/contabilidad/direccion.py`
- `D` `src/cadrumo/domain/contabilidad/errors.py`
- `D` `src/cadrumo/domain/contabilidad/saldo.py`
- `D` `src/cadrumo/domain/contabilidad/tests/__init__.py`
- `D` `src/cadrumo/domain/contabilidad/tests/test_ajuste.py`
- `D` `src/cadrumo/domain/contabilidad/tests/test_cuenta.py`
- `D` `src/cadrumo/domain/contabilidad/tests/test_direccion.py`
- `D` `src/cadrumo/domain/contabilidad/tests/test_saldo.py`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S226.md`
- `verify:` `rg -n 'CONTABILIDAD_|domain\\.contabilidad|AjusteExtracontable|CuentaPgc|ContabilidadDireccion|SaldoCuenta|SumasYSaldos' src/cadrumo dev --glob '*.py' --glob '*.toml'` -> `pass (no matches)`
- `verify:` `uv run --no-sync ruff check src/cadrumo/core/errors/registry/_application_part2.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 --basetemp .tmp/pytest-s226-clean src/cadrumo/core/errors/tests/test_registry.py src/cadrumo/core/errors/tests/test_registry_enforcement.py src/cadrumo/core/errors/tests/test_error_base_binding_order.py src/cadrumo/core/errors/tests/test_error_message_never_blank.py src/cadrumo/domain/calculations/registry/tests/test_modelo_200_base_determination.py src/cadrumo/domain/calculations/registry/tests/test_modelo_200_registry.py` -> `pass (49 passed)`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass (expected nonzero with live findings: 54 unreachable modules, 306 exact unused symbols, 5 orphaned tests, 2029/2084 shipped modules reachable)`

## Notes

A broader `src/cadrumo/core/errors/tests` run passed 72 tests and failed only `test_production_exception_classes_do_not_introduce_unregistered_builtin_roots` on 19 unrelated peer-owned exception classes; none names contabilidad. The focused owning registry and Modelo 200 gates above are clean.
