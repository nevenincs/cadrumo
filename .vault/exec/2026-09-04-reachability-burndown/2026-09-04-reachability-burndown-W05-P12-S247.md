---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:74824d8b5f57aaefd049ae2182ee88d3eebd423622ba660736a06be9e60c7fad'
step_id: 'S247'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
