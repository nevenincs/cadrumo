---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S66'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P07.S66 Registry Schema Verification

Scope: `src/aeat/domain/calculations/registry/tests/test_registry_schema.py`, `src/aeat/domain/calculations/registry/tests`.

## Description

- Verified split schema-family modules with lint and compilation.
- Ran focused schema behavior tests covering core schema, committed registry schema validation, and scalar data-type aliases.
- Verified public registry facade imports for moved schema classes.

## Outcome

Verification passed:

- `uv run --no-sync ruff check --fix src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/_schema_base.py src/aeat/domain/calculations/registry/_schema_scalars.py src/aeat/domain/calculations/registry/_schema_formula.py src/aeat/domain/calculations/registry/_schema_surfaces.py src/aeat/domain/calculations/registry/_schema_input_kind.py src/aeat/domain/calculations/registry/_schema_rounding.py src/aeat/domain/calculations/registry/__init__.py` passed.
- `uv run --no-sync python -m compileall` passed for `_schema.py` and all split schema-family modules.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/tests/test_schema.py src/aeat/domain/calculations/registry/tests/test_registry_schema.py src/aeat/domain/calculations/registry/tests/test_year_data_type.py src/aeat/domain/calculations/registry/tests/test_period_code_data_type.py src/aeat/domain/calculations/registry/tests/test_country_code_data_type.py src/aeat/domain/calculations/registry/tests/test_iban_data_type.py src/aeat/domain/calculations/registry/tests/test_nif_data_type.py src/aeat/domain/calculations/registry/tests/test_long_tail_data_types.py -q` passed: 338 tests.
- Facade smoke import passed for `CasillaDefinition`, `DecimalValue`, `FormulaExpression`, `ParameterDefinition`, `DatedValue`, and `RegistryRoundingCode`.

## Notes

No schema behavior was intentionally changed. The extraction keeps compatibility imports in `_schema.py` because existing domain tests and consumers import schema names from that module directly.
