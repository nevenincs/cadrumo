---
step_id: S327
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W03.P14.S327 — real-behavior tests for AggregationSourceKind relocation

## Outcome

Created `src/aeat/core/test_aggregation.py` (11 tests) with:

- `test_aggregation_source_kind_canonical_module` — asserts `__module__ == "aeat.core.aggregation"`
- `test_aggregation_source_kind_importable_from_core` — importlib identity check
- `test_aggregation_source_kind_members_are_complete` — exact 4-member set assertion
- `test_aggregation_source_kind_values` — snake_case string values
- `test_aggregation_source_kind_roundtrip_pydantic` — parametrized over all 4 members; validates enum identity after pydantic `model_validate`
- `test_aggregation_source_kind_rejects_unknown_value` — `ValidationError` for `"invoice"`
- `test_aggregation_source_kind_roundtrip_json` — full JSON serialise/deserialise cycle
- `test_no_production_module_imports_from_old_source_kinds_location` — AST walk across all `src/aeat/**/*.py` asserting no absolute or relative import from `_source_kinds` module

`pytestmark = [pytest.mark.unit, pytest.mark.domain_core]`. No mocks, no skips, no tautological assertions.

## Files touched

- `src/aeat/core/test_aggregation.py` (new)

## Verification

433 tests pass in targeted run: `uv run --no-sync pytest src/aeat/application/aggregation/ src/aeat/application/review/ src/aeat/core/test_aggregation.py -x`. Inventory test confirms zero remaining imports from the old location.
