---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
---

# Phase 5 Step 10 Execution

Deleted the category-to-casilla projection bridge and fail-closed dependent
runtime paths:

- Removed `src/aeat/domain/categories/_casilla_mapping.py`.
- Removed `CasillaMapping`, `CasillaMappingSign`, and `casilla_mappings` from
  the category public API, profile schema, and 2025 profile registry.
- Removed the `aeat categories casillas` CLI command because categories no
  longer project directly to modelo casillas.
- Replaced financial transaction aggregation with a fail-closed boundary:
  `aggregate_catalogue` validates the modelo and period tokens, then refuses
  casilla aggregation until the central calculation registry has coverage.
- Removed `AggregationCasillaMappingError` and its error-registry entry.
- Removed declaration CLI invoice-to-Modelo-303 casilla projection from
  `_aggregate_filing_inputs`.
- Tightened `CategoryProfile` with `extra="forbid"` so stale
  `casilla_mappings` payloads fail validation instead of being ignored.
- Added deletion gates proving the category bridge cannot be imported or
  exported, application aggregation cannot reference the deleted projection,
  and declaration CLI no longer assigns invoice values into Modelo 303 casillas.

Rationale:

- Spending-category profiles may describe category semantics and legal
  proportionality, but they must not encode filing-layout or modelo-casilla
  truth.
- Financial and invoice-derived filing inputs must come from registry-backed
  calculation definitions, not application-layer shortcuts.
- Coverage gaps must fail hard instead of falling back silently to stale or
  manually projected values.

Verification:

- `uv run --no-sync ruff check src\aeat\domain\categories src\aeat\application\aggregation src\aeat\application\workflow\_adapters.py src\aeat\entrypoints\cli\categories.py src\aeat\entrypoints\cli\_common.py src\aeat\core\errors\registry\_application.py src\aeat\domain\casillas\models.py tests\import_contract\test_registry_deletion_gates.py tests\import_contract\application\aggregation\test_aggregation.py`
- `uv run --no-sync ty check src\aeat\domain\categories src\aeat\application\aggregation src\aeat\application\workflow\_adapters.py src\aeat\entrypoints\cli\categories.py src\aeat\entrypoints\cli\_common.py src\aeat\core\errors\registry\_application.py src\aeat\domain\casillas\models.py tests\import_contract\test_registry_deletion_gates.py tests\import_contract\application\aggregation\test_aggregation.py`
- `uv run --no-sync pytest tests\import_contract\test_registry_deletion_gates.py src\aeat\domain\categories tests\import_contract\application\aggregation\test_aggregation.py src\aeat\application\workflow src\aeat\entrypoints\cli\financial`

Result: ruff passed, ty passed, and the focused pytest slice passed with
134 tests.

Residual risk:

- Financial aggregation and declaration input derivation are intentionally
  fail-closed or empty until registry-backed filing inputs exist.
