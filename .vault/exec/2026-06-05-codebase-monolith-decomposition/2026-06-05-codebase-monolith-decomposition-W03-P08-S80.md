---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S80'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P08.S80 SQL Secure Objects Verification

Scope: verify SQL secure objects persistence behavior and facade imports after decomposition.

## Description

- Run `uv run --no-sync pytest src/aeat/adapters/persistence/storage/sql/tests src/aeat/tests/test_storage_decimal_redaction_error_typing.py -q --tb=short`.
- Run `uv run --no-sync pytest src/aeat/adapters/persistence/storage/sql/tests/test_secure_objects.py src/aeat/adapters/persistence/storage/sql/tests/test_archive_bundle_roundtrip.py src/aeat/tests/test_storage_decimal_redaction_error_typing.py -q`.
- Run `uv run --no-sync pytest src/aeat/adapters/persistence/storage/tests/test_runtime.py src/aeat/adapters/persistence/storage/tests/test_runtime_migrated_repositories.py -q`.
- Run `uv run --no-sync ruff check` over the touched SQL storage files and focused verification surfaces.
- Run `python -m compileall` over the touched SQL secure-object modules.
- Run an import smoke for `SecureObjectRepository`, `SecureObjectRecord`, `SecureObjectWrite`, and `SecureObjectRawRow` through the SQL storage facade and repository module.
- Search application, entrypoint, and domain code for direct imports into the new private SQL secure-object records and crypto modules.

## Outcome

The focused SQL secure-object, archive restore, and storage decimal redaction/error typing tests passed with 70 tests. The runtime storage and migrated-repository tests passed with 126 tests. Ruff and compileall passed for the touched SQL secure-object modules. The facade import smoke succeeded. The private-module consumer search returned no application, entrypoint, or domain imports.

## Notes

The focused SQL verification lane emits three sqlite datetime adapter deprecation warnings from existing SQLAlchemy test execution; no warnings are introduced by the decomposition itself.
