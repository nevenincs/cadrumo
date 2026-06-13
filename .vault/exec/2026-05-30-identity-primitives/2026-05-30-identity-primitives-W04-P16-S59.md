---
step_id: S59
tags:
  - '#exec'
  - '#identity-primitives'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-30-identity-primitives-plan]]'
  - '[[2026-05-30-identity-primitives-adr]]'
  - '[[2026-05-30-identity-primitives-reference]]'
---

# identity-primitives W04.P16.S59 — lift registry-internal BaseModel registry-id fields onto aliases

## Scope

Sweep bare-string registry-id fields on pydantic BaseModels
inside the `domain/calculations/registry` package onto the
typed aliases from `_ids.py` per ADR Rule 8 and Rule 2's
registry-aliases exception.

## Outcome

- `_queries.py` — `ModeloCasillaRow.casilla_id` →
  `CasillaId`, `ModeloBindingRow.binding_id` → `BindingId`,
  `ModeloFormulaRow.formula_id` → `FormulaId`.
- `_bindings.py` — `CasillaObservation.casilla_id` →
  `CasillaId`, `CasillaObservation.formula_id` →
  `FormulaId | None`, `OracleModeloObservation.oracle_id` →
  `OracleId`.
- `_formula_runtime.py` — `RegistryCalculationEntry.formula_id`
  → `FormulaId`.
- `_filed_state.py` — `RegistryFiledStateDrift.casilla_id` →
  `CasillaId`.
- `_live_parity.py` — `ParityResult.oracle_id` /
  `cross_reference_id` → `OracleId` / `CrossReferenceId`;
  `CrossReferenceApplicability.cross_reference_id` →
  `CrossReferenceId`;
  `CrossReferenceApplicabilityDeclaracion.revision_id` /
  `cross_reference_id` → `RevisionId` / `CrossReferenceId`.
- `_export_parse.py` — `ParsedExportFieldValue.record_id` →
  `RecordId`, `.field_id` → `ExportFieldId`, `.casilla_id`
  → `CasillaId | None`, `.binding_id` → `BindingId | None`;
  `ParsedExportPayload.layout_id` → `ExportLayoutId`.

## Skipped per Rule 9 clause 4 narrowing

- Every `_validate_*.py` module: each suspected site lives
  on a `@dataclass(frozen=True, slots=True)` or `Protocol`,
  not a pydantic BaseModel. Out of Rule 9 clause 4 scope.
- `_record_design.DisenoCoverageReport`: dataclass, not
  BaseModel.
- `RegistryModeloObservation.modelo` and
  `CrossReferenceApplicabilityDeclaracion.modelo_id` retain
  `Field(min_length=1, max_length=8/128)`: `ModeloId`'s
  `^\d{3}$` pattern would reject the registry's wider
  modelo strings (narrowing forbidden by brief).

## Verification

- Smoke import test: all 6 modified modules import cleanly.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/`
  background run: 2068 passed, 74 pre-existing failures
  (renta_web_open_replay drift, record_design coverage,
  registry_reviewability baseline, ledger_renta_expense_binding
  date_binding gap, reduccion_art_84_conjunta — none
  type-related; verified by inspecting two failures
  (`test_ledger_renta_expense_binding`,
  `test_cross_dependency_contract`) which surface registry
  data-contract issues unrelated to alias promotion.

## Plan steps closed

`W04.P16.S59`.

## Commits

- `0015524ac` exec(identity-primitives): W04.P16.S59 lift
  registry-internal BaseModel registry-id fields onto aliases
