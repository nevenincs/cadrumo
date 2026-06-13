---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W61.P303.S1818'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-per-modelo-aggregation-pipeline-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-14-cli-workflow-redesign-w61-p303-s1818-code-review-audit]]"
---

# `cli-workflow-redesign` `W61.P303.S1818`

Closed plan rows:

- `W61.P303.S1818`

## Description

Implemented bucket-local modelo aggregation routing for ledger-owned registry bindings and remediated the S1818 review finding.

`resolve_modelo_ledger_binding_values_from_repositories` derives registry binding values from the active bucket transaction catalogue. It routes `ledger_iva_aggregation` through IVA ledger aggregation and `ledger_renta_expense_aggregation` through Renta ledger aggregation. Aggregation issues remain owned by the underlying IVA and Renta aggregators.

`aggregation_period_for_modelo` normalizes modelo filing periods for transaction aggregation. Quarterly tokens such as `1T` and `Q1` resolve to `YYYYQ1`, annual tokens resolve to `YYYY`, and monthly tokens resolve to `YYYY-MM`.

`calculate_modelo_revision_from_bucket_aggregation` loads the modelo work unit, resolves the registry snapshot, derives bucket-local ledger binding values, resolves bound casilla inputs, and delegates to the existing `calculate_modelo_revision` formula-engine path. Formula logic remains centralized in the backend calculation service.

Caller-supplied values cannot override ledger-owned bindings. The service rejects caller `binding_values` whose IDs are owned by `ledger_iva_aggregation` or `ledger_renta_expense_aggregation`, and rejects caller casilla inputs whose casillas are bound to those ledger-owned bindings, including empty-catalogue cases.

`ModeloAggregationBindingError` is exported by the modelo application package and registered as `ERROR_MODELO_AGGREGATION_BINDING`.

The S1818 audit records the initial HIGH bypass finding as resolved, with no HIGH or CRITICAL issues remaining.

## Modified Paths

- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `.vault/audit/2026-05-14-cli-workflow-redesign-W61-P303-S1818-code-review-audit.md`
- `src/aeat/application/aggregation/_modelo_bindings.py`
- `src/aeat/application/aggregation/__init__.py`
- `src/aeat/application/modelo/_actions.py`
- `src/aeat/application/modelo/__init__.py`
- `src/aeat/application/modelo/test_bucket_aggregation_flow.py`
- `src/aeat/core/errors/registry/_domain.py`

## Tests

- `uv run --no-sync ruff check src/aeat/application/aggregation/_modelo_bindings.py src/aeat/application/aggregation/__init__.py src/aeat/application/modelo/_actions.py src/aeat/application/modelo/__init__.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/core/errors/registry/_domain.py`
  - All checks passed
- `uv run --no-sync ty check src/aeat/application/aggregation/_modelo_bindings.py src/aeat/application/aggregation/__init__.py src/aeat/application/modelo/_actions.py src/aeat/application/modelo/__init__.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/core/errors/registry/_domain.py`
  - All checks passed
- `uv run --no-sync pytest src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/modelo/test_file_flow.py src/aeat/application/aggregation/test_iva_ledger.py src/aeat/core/errors/test_registry.py -q`
  - 50 passed

Coverage includes bucket-local transaction catalogue resolution, Modelo 303 IVA ledger binding derivation, calculation delegation through the centralized formula engine, rejection of caller binding overrides, rejection of ledger-bound casilla injection, empty-catalogue override rejection, bucket event emission for the calculation revision, and error-registry coverage for `ModeloAggregationBindingError`.
