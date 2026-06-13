---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S446'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W18.P38.S446 - Close AFR-298 for modelo work plazo

Scope: close `AFR-298` for `src/aeat/application/modelo/_work_plazo.py` with signals `active-profile`, `manifest-bucket`, and `plain-file`; target `manifest-discovery`.

## Description

- Audited filing deadline and recargo summary projection for modelo work units.
- Confirmed deadline and recargo logic is delegated to domain deadline services.
- Repaired the overdue recargo fallback so it catches only `DeadlineValidationError`,
  logs the typed registry failure at debug level, and lets unexpected exceptions
  propagate.
- Closed `W18.P38.S446` and updated the `AFR-298` register status to `closed`.

## Outcome

`AFR-298` is closed as `manifest-discovery`. The module computes read-only deadline summaries over a supplied work unit and does not own persistence or storage routing.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/modelo/_selectors.py src/aeat/application/modelo/_work_addressing.py src/aeat/application/modelo/_work_create_policy.py src/aeat/application/modelo/_work_plazo.py src/aeat/application/modelo/_iva_wallet_seed.py src/aeat/entrypoints/cli/_modelo_projection_cli.py src/aeat/entrypoints/cli/_modelo_iva_wallet_cli.py src/aeat/domain/deadlines/tests/test_recargo.py src/aeat/application/modelo/tests/test_selectors.py src/aeat/application/modelo/tests/test_work_addressing.py src/aeat/application/modelo/tests/test_export.py src/aeat/entrypoints/cli/tests/test_modelo_projection.py src/aeat/entrypoints/cli/tests/test_ledger_verb_spine.py src/aeat/entrypoints/cli/tests/test_iva_wallet_inspector.py`
- `uv run --no-sync pytest -q src/aeat/domain/deadlines/tests/test_recargo.py src/aeat/application/modelo/tests/test_selectors.py src/aeat/application/modelo/tests/test_work_addressing.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_iva_wallet_inspector.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_modelo_projection.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_ledger_verb_spine.py -k modelo`
- `uv run --no-sync pytest -q src/aeat/application/modelo/tests/test_export.py -k "wallet or exportable or projection"`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py`
- `uv run --no-sync pytest -q src/aeat/core/errors/tests/test_registry_enforcement.py src/aeat/core/errors/tests/test_registry.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

## Notes

Source change made in `_work_plazo.py`.
