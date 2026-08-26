---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:5b2f43ed4df2ee68ecada5ff3eda86c7f12ca2726537b6ca6ae72d352f74b9b3'
step_id: 'S261'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Retire the 11 detail_record_bindings re-export(s) from the registry bindings dispatch module by direct-importing AtributionMemberObservation, Modelo720RowObservation, RefundOperationObservation, RelatedPartyOperationObservation, _build_foreign_asset_rows, _build_related_party_rows and others from their defining module at every production, test, fixture, annotation, tooling and dynamic consumer, delete the corresponding __all__ entries and import block, and prove zero remaining reach through the dispatch module for those symbols.

## Scope

- `src/cadrumo/domain/calculations/registry/detail_record_bindings.py`
- `src/cadrumo/domain/calculations/registry/bindings.py`
- `and every consumer of the listed symbols under src/`
- `dev/ and docs/`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_detail_record_row_builders.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_detail_record_row_builders.py src/cadrumo/domain/calculations/registry/tests/test_detail_record_modelo_coverage.py src/cadrumo/domain/calculations/registry/tests/test_detail_record_observations.py src/cadrumo/domain/calculations/registry/tests/test_foreign_asset_binding_row_field.py -q -m unit` -> `pass` (69 passed)

## Notes

The four validate_* dispatch-table entries for ATRIBUCION_MEMBER, FOREIGN_ASSET, REFUND_OPERATION and RELATED_PARTY_OPERATION stay -- genuine dispatch role, never in __all__, out of this Step's named scope.
