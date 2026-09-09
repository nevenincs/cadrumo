---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:f120c5ac037cbebf38a78f1a879b1828a3f89e7ead2d543d6cf1df344adf5f51'
step_id: 'S247'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the now-ownerless EncryptedString SQLAlchemy decorator exposed by the fincas withdrawal.

## Scope

- `Retain HashedLookup and secure-object row-bound encryption`
- `remove EncryptedString-only test schema and prose`
- `run focused crypto gates`
- `remeasure exact reachability`
- `update the cadence reference`
- `and write the Step Record.`

## Changes

- `M` `src/cadrumo/adapters/persistence/storage/crypto/encrypted_columns.py`
- `M` `src/cadrumo/adapters/persistence/storage/crypto/__init__.py`
- `M` `src/cadrumo/adapters/persistence/storage/__init__.py`
- `M` `src/cadrumo/adapters/persistence/storage/envelope/secure_bound_repository.py`
- `M` `src/cadrumo/adapters/persistence/storage/crypto/tests/test_encrypted_columns.py`
- `M` `src/cadrumo/adapters/persistence/storage/crypto/tests/test_type_guard_errors.py`
- `M` `src/cadrumo/application/calculations/tests/_observation_lookup_support.py`
- `M` `src/cadrumo/application/calculations/tests/test_modelo_347_informativa_fidelity.py`
- `M` `src/cadrumo/application/calculations/tests/test_modelo_184_informativa_fidelity.py`
- `M` `src/cadrumo/application/calculations/tests/test_modelo_232_operaciones_vinculadas_fidelity.py`
- `M` `src/cadrumo/application/calculations/tests/test_modelo_036_censal_continuity.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check <focused S247 paths>` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 -m "" src/cadrumo/adapters/persistence/storage/crypto/tests/test_encrypted_columns.py src/cadrumo/adapters/persistence/storage/crypto/tests/test_type_guard_errors.py src/cadrumo/adapters/persistence/storage/sql/tests src/cadrumo/adapters/persistence/storage/envelope/tests` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The exact zero-target detector remains red on the live backlog. This Step reduced exact unused symbols from 292 to 291 while retaining 34 unreachable modules, 1 type-only module, and 0 orphan tests. Focused crypto, SQL, and secure-envelope verification passed 214 tests.
