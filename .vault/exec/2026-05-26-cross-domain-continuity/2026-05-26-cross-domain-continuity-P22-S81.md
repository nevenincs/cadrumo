---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
step_id: S81
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity P22.S81

## Outcome

Added `LedgerRentaIncomeAggregationSourceResolver` to
`src/aeat/application/aggregation/_modelo_bindings.py`:

- `resolver_id = "ledger_renta_income_aggregation"`, `owned_sources = ("ledger_renta_income_aggregation",)`
- `resolve()` short-circuits via `_revision_has_binding_source` when M130 carries no income binding
- Delegates to `aggregate_renta_income_ledger_from_repositories` (S82), converts observations
  through `resolve_ledger_renta_income_aggregation_binding_values`, emits
  `CalculationSourceProvenance` per transaction and `CalculationSourceDiagnostic` per issue
- `renta_income_issues` field added to `ModeloLedgerBindingAggregation` with freeze-validator
  and serializer in parity with the existing `renta_issues` pattern
- `resolve_modelo_ledger_binding_values_from_repositories` extended with the
  `ledger_renta_income_aggregation` branch
- `LedgerRentaIncomeAggregationSourceResolver` added to `__all__`

Domain registry changes (same commit):
- `"ledger_renta_income_aggregation"` added to `DataBindingDefinition.source` Literal union
  in `_schema.py`
- `_RentaLedgerIncomeSelector`, `validate_ledger_renta_income_aggregation_binding_definition`,
  `RentaIncomeObservationProtocol`, `resolve_ledger_renta_income_aggregation_binding_values`
  added to `_bindings.py`; registered in `_BINDING_SELECTOR_REGISTRY` and `__all__`
- Validator registered in `_validate_record_sections.py` source_validators table
- Three symbols exported from `registry/__init__.py`

Locale key `aggregation.renta_ledger.errors.quarterly_period_required` added via scaffold;
translated in ca/en/es; hu stub preserved.

## Commit

`3445eb6cf` — S81+S82: M130 actividad-economica income aggregation resolver + ledger module
