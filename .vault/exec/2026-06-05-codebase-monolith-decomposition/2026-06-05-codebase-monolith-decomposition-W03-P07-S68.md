---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S68'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P07.S68 Registry Record Design Verification

Scope: `src/aeat/domain/calculations/registry/tests src/aeat/tests`.

## Description

- Verify record-design parser and coverage behavior after model extraction.
- Verify package facade identity for `RecordDesignField` and `RecordDesignSheet`.
- Verify no application, entrypoint, or domain consumer imports the new private record-design schema module directly.
- Run public API and cross-module import guard checks.
- Run ruff over the touched record-design modules.

## Outcome

Verification passed for the record-design surface:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/tests/test_record_design.py -q --tb=short` passed with 41 tests.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/tests/test_public_api_boundaries.py ...` passed its 5 registry public API tests.
- Package facade smoke import confirmed `RecordDesignField` and `RecordDesignSheet` resolve from `_record_design_schema` while `_record_design.py` preserves the same object identity.
- `rg` found no application, entrypoint, or domain imports into `_record_design_schema`.
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_record_design.py src/aeat/domain/calculations/registry/_record_design_schema.py` passed.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-06-05-codebase-monolith-decomposition-plan.md` passed with only existing warning `PLAN022`.

Residual unrelated guard:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/tests/test_public_api_boundaries.py src/aeat/tests/test_cross_module_imports_resolve.py -q --tb=short` had 7 passed and 1 failed. The failure is the pre-existing cross-module `__all__` drift in `aeat/core/access_gate/__init__.py`, `aeat/domain/contribuyente/assets/__init__.py`, `aeat/domain/contribuyente/inventory/__init__.py`, and `aeat/entrypoints/cli/_config/__init__.py`, not a registry record-design regression.

## Notes

The cross-module `__all__` drift is tracked as a broader residual guard issue from earlier verification and remains outside this record-design slice.
