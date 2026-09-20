---
tags:
  - '#exec'
  - '#lud-authority'
date: '2026-09-20'
modified: '2026-09-20'
body_schema: 'body-v2'
body_hash: 'sha256:e567e49af621a4b65c7aa5b23fad4d5e2600604dee174a82b3e6c1d71946bf3c'
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
- `S02` `M` `packaging/authority/hatch_build.py`
- `S02` `M` `src/cadrumo/adapters/persistence/profile/transactions.py`
- `S02` `M` `src/cadrumo/application/modelo/_transaction_catalogue_cache.py`
- `S02` `M` `src/cadrumo/application/modelo/calculation_actions.py`
- `S02` `M` `src/cadrumo/application/modelo/tests/test_memoized_transaction_catalogue_repository.py`
- `S02` `M` `src/cadrumo/application/user_profile/profile_record_repository.py`
- `S02` `M` `src/cadrumo/conftest.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/config/tests/test_profile_complete_setup_verb.py`
- `S02` `M` `.vault/audit/2026-09-20-lud-authority-audit.md`
- `S02` `verify:` `just check-code` -> `pass`
- `S02` `verify:` `just test-ci-contracts` -> `pass`
- `S02` `verify:` `just test-gate origin/main` -> `pass`
- `S02` `verify:` `just check-security-diff origin/main` -> `pass`
- `S02` `verify:` `just check-registry-gate` -> `pass`
- `S02` `verify:` `vaultspec-core vault check all --feature lud-authority` -> `pass`
- `S02` `M` `dev/quality/types.py`
- `S02` `M` `dev/quality/tests/test_types_gate.py`
- `S02` `verify:` `Linux Python 3.13.11 just check-types` -> `pass`
- `S02` `verify:` `pytest dev/quality/tests/test_types_gate.py` -> `pass`
- `S02` `verify:` `just check-code after type scheduler repair` -> `pass`
- `S02` `verify:` `just test-gate origin/main after type scheduler repair` -> `pass`
- `S02` `M` `dev/release/tests/test_distribution_readiness.py`
- `S02` `M` `dev/ci/tests/test_ledger_scale_benchmark.py`
- `S02` `verify:` `platform-independent distribution evidence conflict contract` -> `pass`
- `S02` `verify:` `isolated 30000-row Modelo 130 CPU benchmark at unchanged ceiling` -> `pass`
- `S02` `verify:` `just test-ci-contracts after Linux scoped-gate repair` -> `pass`

## Notes

- `S02` just check-code retains 17 unrelated type diagnostics plus pre-existing import-boundary, dependency-declaration, reachability, symbol-usage, export-consumption, and docstring-reference failures outside this feature; style, format, data-format, and secure/persistence write-path gates pass.
- `S02` just test-gate retains 64 pre-existing failures in dev/tests/test_import_quality_gate.py caused by the branch import-gate event/schema and count mismatch; 64 tests pass and no Lud Authority feature file appears in those failures.
- `S02` The full Vaultspec pipeline retains 25 errors and 507 warnings in other features: 24 legacy execution-mapping errors, one unrelated ungrounded ADR schema error, and historical corpus warnings; all Lud Authority scoped checks pass.
- `S02` Unscoped historical corpus remains outside Lud Authority: 26 feature warnings, 116 execution-mapping findings, 392 body-section findings, and one unrelated ADR grounding error; the feature-scoped check is clean.
- `S02` Post-push Linux lint exposed same-checker process multiplication in the existing cross-platform type orchestrator; the scheduler now preserves all nine measurements while serializing each checker family's platform sweep.
- `S02` Post-push Linux scoped contracts exposed a Linux-matching conflict fixture and one contended CPU benchmark; the fixture is platform-independent and the benchmark now runs in the existing serial performance lane without changing its threshold or control.
