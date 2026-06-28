---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S72'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P07.S72 Registry Workbook Parity Verification

Scope: `src/aeat/domain/calculations/registry/tests src/aeat/adapters/outbound/google/tests`.

## Description

- Verify workbook parity behavior after status/type and model-contract extraction.
- Verify `_workbook_parity.py` still resolves workbook parity type and model symbols from the new private modules.
- Verify no application, entrypoint, or domain consumer imports `_workbook_parity_types` or `_workbook_parity_models` directly.
- Run outbound Google tests named in the verification scope.
- Run ruff over the touched workbook parity modules.
- Confirm `_workbook_parity.py` is below the 1250-line module target after the split.

## Outcome

Verification passed:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/tests/test_workbook_parity.py src/aeat/domain/calculations/registry/tests/test_public_api_boundaries.py -q --tb=short` passed with 23 tests.
- `uv run --no-sync pytest src/aeat/adapters/outbound/google/tests -q --tb=short` passed with 152 tests and 3 deselected.
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_workbook_parity.py src/aeat/domain/calculations/registry/_workbook_parity_models.py src/aeat/domain/calculations/registry/_workbook_parity_types.py` completed cleanly.
- `_workbook_parity.py` smoke import resolved `WorkbookKind` from `_workbook_parity_types` and `WorkbookCellRef` from `_workbook_parity_models`.
- `rg` found no application, entrypoint, or domain imports into `_workbook_parity_types` or `_workbook_parity_models`.
- `_workbook_parity.py` is 1076 lines after the split; `_workbook_parity_models.py` is 161 lines; `_workbook_parity_types.py` is 30 lines.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-06-05-codebase-monolith-decomposition-plan.md` completed with only existing warning `PLAN022`.

## Notes

The plan warning `PLAN022` remains the known canonical-id monotonicity warning from earlier plan structure, not a workbook parity decomposition failure.
