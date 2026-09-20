---
tags:
  - '#exec'
  - '#lud-authority'
date: '2026-09-20'
modified: '2026-09-20'
body_schema: 'body-v2'
body_hash: 'sha256:57d81c8c8283090609065624308d14e93638fe1b0c4d8467c1f49eaff67e5bad'
related:
  - "[[2026-09-20-lud-authority-plan]]"
---

# `lud-authority` ledger

## Changes

- `S01` `M` `src/cadrumo/core/storage_materialization.py`
- `S01` `M` `src/cadrumo/core/storage_taxonomy_locations.py`
- `S01` `M` `src/cadrumo/core/tests/test_ensure_storage_tree.py`
- `S01` `A` `.vault/reference/2026-09-20-lud-authority-reference.md`
- `S01` `A` `.vault/adr/2026-09-20-lud-authority-adr.md`
- `S01` `A` `.vault/plan/2026-09-20-lud-authority-plan.md`
- `S01` `A` `.vault/index/lud-authority.index.md`
- `S01` `verify:` `ruff and three module type checkers` -> `pass`
- `S01` `by:` `principal executor`
- `S02` `M` `.vault/plan/2026-09-20-lud-authority-plan.md`
- `S02` `M` `src/cadrumo/application/provisioning.py`
- `S02` `M` `src/cadrumo/application/tests/test_provisioning.py`
- `S02` `M` `src/cadrumo/core/storage_materialization.py`
- `S02` `M` `src/cadrumo/core/storage_taxonomy_locations.py`
- `S02` `M` `src/cadrumo/core/tests/test_ensure_storage_tree.py`
- `S02` `M` `src/cadrumo/domain/calculations/registry/authority_store.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/main.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/tests/test_cli_startup_smoke.py`
- `S02` `verify:` `just test-gate` -> `fail`
- `S02` `by:` `principal executor`
- `S02` `M` `.vault/adr/2026-09-20-lud-authority-adr.md`
- `S02` `M` `.vault/reference/2026-09-20-lud-authority-reference.md`
- `S02` `verify:` `focused storage and application tests` -> `pass`
- `S02` `verify:` `CLI startup metadata and side-effect integration tests` -> `pass`
- `S02` `verify:` `ruff and three production-module type checkers` -> `pass`
- `S02` `verify:` `logging binding gate` -> `pass`
- `S02` `verify:` `just check-code` -> `fail`
- `S02` `verify:` `vaultspec-core vault check all` -> `fail`

## Notes

- `S02` just check-code retains 17 unrelated type diagnostics plus pre-existing import-boundary, dependency-declaration, reachability, symbol-usage, export-consumption, and docstring-reference failures outside this feature; style, format, data-format, and secure/persistence write-path gates pass.
- `S02` just test-gate retains 64 pre-existing failures in dev/tests/test_import_quality_gate.py caused by the branch import-gate event/schema and count mismatch; 64 tests pass and no Lud Authority feature file appears in those failures.
- `S02` The full Vaultspec pipeline retains 25 errors and 507 warnings in other features: 24 legacy execution-mapping errors, one unrelated ungrounded ADR schema error, and historical corpus warnings; all Lud Authority scoped checks pass.
