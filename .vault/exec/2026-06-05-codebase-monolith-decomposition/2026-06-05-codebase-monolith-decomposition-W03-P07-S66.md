---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
step_id: 'S66'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P07.S66 Registry Schema Verification

Scope: `src/aeat/domain/calculations/registry/tests/test_registry_schema.py src/aeat/domain/calculations/registry/tests`.

## Description

- Verify `InputKind` and `RegistryRoundingCode` still resolve through `aeat.domain.calculations.registry`.
- Verify `_schema.py` still re-exports the moved typed-axis symbols for existing internal imports.
- Run focused schema, internal-only casilla, and referential-integrity tests.
- Run ruff over the decomposed schema files.

## Outcome

Verification passed:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/tests/test_schema.py src/aeat/domain/calculations/registry/tests/test_internal_only_casilla.py src/aeat/domain/calculations/registry/tests/test_referential_integrity.py -q --tb=short` passed with 71 tests.
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/_schema_input_kind.py src/aeat/domain/calculations/registry/_schema_rounding.py` passed.
- Package facade smoke import confirmed `InputKind` resolves from `_schema_input_kind` and `RegistryRoundingCode` resolves from `_schema_rounding` while preserving `_schema` identity re-exports.
- `rg` found no application or CLI imports into the new private schema typed-axis modules.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-06-05-codebase-monolith-decomposition-plan.md` passed with only existing warning `PLAN022`.

## Notes

The plan warning `PLAN022` remains the known canonical-id monotonicity warning from earlier plan structure, not a schema decomposition failure.
