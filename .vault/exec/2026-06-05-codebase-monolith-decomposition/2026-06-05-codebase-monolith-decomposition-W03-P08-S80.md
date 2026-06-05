---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
step_id: 'S80'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P08.S80 SQL Secure Objects Verification

Scope: verify SQL secure objects persistence behavior and facade imports after decomposition.

## Description

- Run `uv run --no-sync pytest src/aeat/adapters/persistence/storage/sql/tests src/aeat/tests/test_storage_decimal_redaction_error_typing.py -q --tb=short`.
- Run `uv run --no-sync ruff check` over the touched SQL storage files and focused verification surfaces.
- Run an import smoke for `SecureObjectRepository`, `SecureObjectRecord`, `SecureObjectWrite`, and `SecureObjectRawRow` through the SQL storage facade and repository module.
- Search application, entrypoint, and domain code for direct imports into the new private SQL secure-object records and crypto modules.

## Outcome

SQL storage tests and the focused storage decimal redaction/error typing test passed with 92 tests. Ruff passed for the touched storage and test files. The facade import smoke succeeded. The private-module consumer search returned no application, entrypoint, or domain imports.

## Notes

The verification lane emits five sqlite datetime adapter deprecation warnings from existing SQLAlchemy test execution; no warnings are introduced by the decomposition itself.
