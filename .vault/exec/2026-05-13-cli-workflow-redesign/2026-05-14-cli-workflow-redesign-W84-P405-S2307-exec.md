---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'S2307'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-per-modelo-aggregation-pipeline-adr]]'
---

# `cli-workflow-redesign` `W84.P405.S2307`

Completed the corrective application counterpart aggregation slice for Modelos 347 and 349.

- Modified: `src/aeat/application/aggregation/_counterpart.py`
- Modified: `src/aeat/application/aggregation/__init__.py`
- Modified: `src/aeat/application/aggregation/test_counterpart.py`

## Description

Baseline verification found the plan row already checked, but the implementation only partially satisfied the row: `CounterpartObservation` rejected bare `invoice` while still accepting arbitrary noncanonical source kinds, rollups merged different source-kind cohorts for the same counterparty and operation kind, the package API did not re-export counterpart aggregation types, and 349 GROI / NIF-IVA readiness was only documented as a downstream concern.

The implementation now enforces the four-source taxonomy exactly at the app aggregation boundary: `ledger_transaction`, `purchase_invoice_evidence`, `payable_invoice`, and `collectible_invoice`. The rejected bare `invoice` and conceptual `business_operation` labels both fail validation rather than being normalized or shimmed.

Counterpart rollups now carry `source_kind` and aggregate by `(source_kind, counterparty_nif, operation_kind)`, preventing canonical fact streams from being silently merged. Modelo 349 rollups also carry explicit readiness fields: Spanish counterparties require GROI readiness, and non-Spanish counterparties require NIF-IVA readiness before the row is treated as declarable-ready. The public `aeat.application.aggregation` package now exports the counterpart aggregation models and functions.

Focused review found that cohort splitting made the old per-rollup Modelo 347 threshold helper unsafe. The helper now evaluates a full `CounterpartAggregation` plus counterparty NIF, and `declarable_counterparty_nifs_347` sums every source-kind and operation-kind cohort before applying the €3,005.06 floor. Public rollups now validate source kind and country shape directly, not only through observation construction.

Final review found one remaining 349 ordering hazard: conflicting countries inside the same `(source_kind, counterparty_nif, operation_kind)` cohort could change readiness depending on input order. The aggregator now rejects that cohort as invalid. Country validation is also ASCII alpha-2, so non-ASCII uppercase letters are rejected rather than accepted by Python Unicode `isalpha()`.

## Tests

Focused verification passed:

- `uv run --no-sync pytest -q src/aeat/application/aggregation/test_counterpart.py`
- `uv run --no-sync pytest -q src/aeat/application/aggregation/test_counterpart.py src/aeat/application/aggregation/test_retenciones.py`
- `uv run --no-sync pytest -q src/aeat/application/aggregation/test_counterpart.py src/aeat/domain/calculations/registry/test_counterpart_bindings.py src/aeat/domain/calculations/registry/test_modelo_349_registry.py` passed 106 tests
- `uv run --no-sync pytest --collect-only -q src/aeat/application/aggregation` collected 171 tests
- `uv run --no-sync ruff check src/aeat/application/aggregation/_counterpart.py src/aeat/application/aggregation/test_counterpart.py src/aeat/application/aggregation/__init__.py`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md --json`
- `git diff --check -- src/aeat/application/aggregation/_counterpart.py src/aeat/application/aggregation/test_counterpart.py src/aeat/application/aggregation/__init__.py`
