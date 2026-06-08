---
tags:
  - '#audit'
  - '#repo-health-diagnostics'
date: '2026-06-08'
related:
  - '[[2026-06-04-full-repo-health-diagnostics-audit]]'
---

# `repo-health-diagnostics` audit: `database-codebase-health`

## Scope

This audit reviews the code health, static typecheck compliance, and complexity footprint of the database and SQL persistence layers of the repository. Scanned targets include `src/aeat/adapters/persistence/storage/sql/` and adjacent database modules. Diagnostics were gathered via `ty`, `pyright`, `radon`, and `complexipy` running under the virtual environment.

## Findings

### HEALTH-DB-001 | MEDIUM | Typecheck compliance issues in SQL schema and repository classes

The typecheck suite `ty check src/aeat/adapters/persistence/storage/sql/` reports 17 diagnostics in SQL production and test modules:

- **Missing Overrides:** Subclass repositories `ModeloRepository`, `PortalRepository`, and `CorpusArtifactRepository` in `src/aeat/adapters/persistence/storage/sql/repository.py` override overridden base class methods `list_all`, `get`, `upsert`, and `delete` from `SqlRecordRepository` without the `@override` decorator. This accounts for 12 diagnostics.
- **Narrowing Defect:** In `src/aeat/adapters/persistence/storage/sql/_secure_object_schema.py` line 199, `bytes(value)` is invoked on `value: object` without type narrowing, raising `invalid-argument-type` (expected `Iterable[SupportsIndex] | SupportsIndex | SupportsBytes | Buffer`, found `~bytes & ~bytearray & ~memoryview[int] & ~str`).

### HEALTH-DB-002 | MEDIUM | Test-only typechecker errors on SQL fixtures and helper functions

The static type checker reports 4 test-related diagnostics in the SQL test suite:

- **SQLAlchemy Table Insert attribute:** In `src/aeat/adapters/persistence/storage/sql/tests/test_secure_objects_part1.py` line 287 and `src/aeat/adapters/persistence/storage/sql/tests/test_secure_objects_part2.py` line 507, `SecureObjectRow.__table__.insert()` raises `unresolved-attribute` because `__table__` resolves to a `FromClause` which lacks the `insert` method definition in the current stubs.
- **Dynamic Connection Hook argument type:** In `src/aeat/adapters/persistence/storage/sql/tests/test_secure_objects_part2.py` line 125, `context.execution_options` raises `unresolved-attribute` because the parameter `context` is annotated as `object`.
- **Validation test parameter mismatch:** In `src/aeat/adapters/persistence/storage/sql/tests/test_secure_objects_part2.py` line 633, `SecureObjectWrite` is constructed with `conflict_policy="compare-and-swap"`, raising `unknown-argument`. This constructor call is designed to fail runtime validation inside a `pytest.raises(ValidationError)` block, but triggers a static type warning.

### HEALTH-DB-003 | LOW | One complexity hotspot in secure-object migration code

Radon and Complexipy analysis identifies one function above the project's cognitive complexity threshold of 20:

- `src/aeat/adapters/persistence/storage/sql/_secure_object_migration.py::ensure_deterministic_object_keys` has a cyclomatic complexity of 13 (Grade C) and a cognitive complexity of 26.
- Method complexity within the core class `SecureObjectRepository` in `src/aeat/adapters/persistence/storage/sql/secure_objects.py` is moderate: `_save_internal_in_session` has Grade B (10), `iter_records_with_failures` has Grade B (9), `_check_session_freshness` has Grade B (8), and `iter_all_records_raw` has Grade B (8).

### HEALTH-DB-004 | INFO | Unit test suite runs green with no regressions

The test suite `src/aeat/adapters/persistence/storage/sql/tests` passes 67 unit tests with 5 deprecation warnings relating to SQLite datetime adapters under Python 3.12/3.13. No regressions are reported.

## Recommendations

1. **Add Override Decorators:** Decorate `list_all`, `get`, `upsert`, and `delete` in subclass repositories within `src/aeat/adapters/persistence/storage/sql/repository.py` with `@override` (imported from `typing`) to resolve the linter diagnostics.
2. **Refactor byte coercion:** Replace the blind `bytes(value)` fallback on line 199 in `src/aeat/adapters/persistence/storage/sql/_secure_object_schema.py` with explicit check or coercion logic (e.g., throwing a `ValueError` or using custom conversions if the object type is unsupported).
3. **Type Annotation Escapes in Tests:** Cast or override variables to correct the unresolved attribute warnings in tests (e.g., typing `context` as a specific connection context instead of `object`, and passing dictionary arguments via `**{...}` splat to bypass static parameters validation for error-testing).
4. **Isolate Migration Complexity:** Keep `ensure_deterministic_object_keys` under advisory tracking. Refactoring this method is not urgent because it is isolated to the migration helper module and has a cognitive complexity of 26, which is close to the threshold of 20.

## Codification candidates

None.
