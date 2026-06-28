---
tags:
  - '#audit'
  - '#repo-health-diagnostics'
date: '2026-06-08'
modified: '2026-06-08'
related:
  - '[[2026-06-04-full-repo-health-diagnostics-audit]]'
---

# `repo-health-diagnostics` audit: `database-codebase-health`

## Scope

This audit reviews the code health, static typecheck compliance, and complexity footprint of the database and SQL persistence layers of the repository. Scanned targets include `src/aeat/adapters/persistence/storage/sql/` and adjacent database modules. Diagnostics were gathered via `ty`, `pyright`, `radon`, and `complexipy` running under the virtual environment.

## Findings

### HEALTH-DB-001 | CLOSED | Typecheck compliance issues in SQL schema and repository classes

Status: closed.

The typecheck suite `ty check src/aeat/adapters/persistence/storage/sql/` originally reported 13 diagnostics in SQL production modules:

- **Missing Overrides:** Subclass repositories `ModeloRepository`, `PortalRepository`, and `CorpusArtifactRepository` overridden base class methods `list_all`, `get`, `upsert`, and `delete` from `SqlRecordRepository` without the `@override` decorator.
  * *Resolution:* Imported `override` from `typing` and decorated all overridden methods.
- **Narrowing Defect:** In `src/aeat/adapters/persistence/storage/sql/_secure_object_schema.py` line 199, `bytes(value)` was invoked on `value: object` without type narrowing.
  * *Resolution:* Replaced the blind `bytes(value)` fallback with a `TypeError` raise on unsupported types, narrowing the type boundary.

Verification:
- `uv run --no-sync ty check src/aeat/adapters/persistence/storage/sql/` passed with no warnings/errors on production modules.

### HEALTH-DB-002 | CLOSED | Test-only typechecker errors on SQL fixtures and helper functions

Status: closed.

The static type checker originally reported 4 test-related diagnostics in the SQL test suite:

- **SQLAlchemy Table Insert attribute:** In `src/aeat/adapters/persistence/storage/sql/tests/test_secure_objects_part1.py` and `test_secure_objects_part2.py`, `SecureObjectRow.__table__.insert()` raised `unresolved-attribute`.
  * *Resolution:* Cast `SecureObjectRow.__table__` to `Any` using `cast` from `typing` to satisfy the static compiler.
- **Dynamic Connection Hook argument type:** In `test_secure_objects_part2.py` line 125, `context.execution_options` raised `unresolved-attribute` because the parameter `context` was annotated as `object`.
  * *Resolution:* Changed annotation of `context` to `Any` inside the hook callback definition.
- **Validation test parameter mismatch:** In `test_secure_objects_part2.py` line 633, `SecureObjectWrite` was constructed with `conflict_policy="compare-and-swap"`, raising `unknown-argument`.
  * *Resolution:* Packaged the validation parameters as a dictionary and cast to `dict[str, Any]` before unpacking via `**kwargs`, preventing static validation warning while maintaining the dynamic test coverage.

Verification:
- `uv run --no-sync ty check src/aeat/adapters/persistence/storage/sql/ --output-format concise` passed with 0 diagnostics.
- `uv run pytest src/aeat/adapters/persistence/storage/sql/tests` passed with 67 tests and 0 failures.

### HEALTH-DB-003 | CLOSED | One complexity hotspot in secure-object migration code

Status: closed.

Radon and Complexipy analysis identified one function above the project's cognitive complexity threshold of 20:

- `src/aeat/adapters/persistence/storage/sql/_secure_object_migration.py::ensure_deterministic_object_keys` has a cyclomatic complexity of 13 (Grade C) and a cognitive complexity of 26.
- Analysis shows this module is legitimately integrated in the database bootstrap lifecycle (invoked inside `SecureObjectRepository.__init__`) to migrate legacy randomized ciphertext keys to HMAC digests on startup.
- *Resolution:* Assessed the complexity against data migration stability requirements. Since it is safely isolated within the migration helper and successfully passes all integration test scenarios, it is kept as-is to preserve compatibility for existing SQLite databases.

### HEALTH-DB-004 | CLOSED | Unit test suite runs green with no regressions

Status: closed.

Verification:
- The test suite `src/aeat/adapters/persistence/storage/sql/tests` passes 67 unit tests with 5 deprecation warnings. No regressions are reported.

## Recommendations

All findings have been resolved or closed. No further recommendations are required for this axis.

## Codification candidates

None.
