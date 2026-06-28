---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-w12-p23-s94-explicit-route-guard-exec]]'
---

# `secure-storage-production-hardening` `W12.P23.S95` Test-Isolation Closeout

## Scope

This audit closes the S93-S95 test-isolation sweep for explicit database-route setup. S93 migrated repeated fixture-level custody setup to centralized runtime helpers where the tests were exercising normal profile-backed behavior. S94 now rejects new unapproved executable `aeat_database_url` / `AEAT_DATABASE_URL` setup outside the approved inventory below.

## Approved Residual Categories

### Low-level SQL and envelope substrate

These files intentionally construct explicit SQLite routes because their subject is the SQL engine, encrypted-object repository substrate, archive-bundle behavior, constraint behavior, or secure-bound adapter contract:

- `src/aeat/adapters/persistence/storage/sql/test_engine.py`
- `src/aeat/adapters/persistence/storage/sql/test_session.py`
- `src/aeat/adapters/persistence/storage/sql/test_repository.py`
- `src/aeat/adapters/persistence/storage/sql/test_constraints.py`
- `src/aeat/adapters/persistence/storage/sql/test_archive_bundle_roundtrip.py`
- `src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
- `src/aeat/adapters/persistence/storage/envelope/_repository_test_suite.py`
- `src/aeat/adapters/persistence/storage/envelope/test_secure_bound_repository.py`
- `src/aeat/adapters/persistence/storage/envelope/test_secure_bound_repository_contract.py`

Owning behavior: low-level substrate tests prove encrypted SQL persistence and repository semantics without routing through the profile runtime. These remain approved because they are below the runtime policy boundary.

### Runtime route classification and guard policy

These files intentionally use explicit routes because their subject is route classification, runtime refusal, route precedence, or the guard itself:

- `src/aeat/adapters/persistence/storage/test_runtime.py`
- `src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`
- `src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py`
- `src/aeat/core/test_storage_route_classification.py`

Owning behavior: these tests assert the centralized settings/runtime route rules. They are the approved place to describe or exercise explicit route handling directly.

### Application and CLI refusal contracts

These files intentionally retain explicit-route setup because they assert that higher-level application or CLI boundaries refuse explicit database routing, preserve cold-start behavior, or avoid leaking raw internal errors:

- `src/aeat/application/test_storage_write_policy.py`
- `src/aeat/application/workflow/test_runtime_defaults.py`
- `src/aeat/application/test_state_projection.py`
- `src/aeat/application/test_diagnostics.py`
- `src/aeat/application/test_repair_integrity.py`
- `src/aeat/application/user_profile/test_repository.py`
- `src/aeat/entrypoints/cli/test_root_fallback_write_guard.py`
- `src/aeat/entrypoints/cli/test_cold_start_no_profile.py`
- `src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py`

Owning behavior: these tests pin refusal, diagnostics, repair, and cold-start contracts. They remain approved only insofar as they test explicit-route refusal/classification or raw-error non-leak behavior.

### Shared settings and test-helper boundary

These files intentionally retain explicit-route references because they test or implement the centralized settings/test helper boundary itself:

- `src/aeat/tests/secure_sql.py`
- `src/aeat/tests/test_secure_sql.py`
- `src/aeat/tests/test_config.py`

Owning behavior: `secure_sql.py` is the sanctioned helper layer for low-level explicit SQL isolation and runtime profile setup. `test_secure_sql.py` and `test_config.py` assert the settings/helper behavior and explicit route precedence contracts.

## Guard Contract

`src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py` now scans executable test and shared test-helper sources for `aeat_database_url`, `AEAT_DATABASE_URL`, and embedded executable string constants. Any new executable hit outside the approved inventory fails the guard. Docstring-only narrative mentions are ignored so tests can describe the route policy without becoming false positives.

## Remaining Follow-Up

- The guard is file-level, not call-site-level. Additional explicit-route setup inside an approved file will not fail the guard automatically; maintainers must keep those files within the owning behavior above.
- Several remaining `dispose_engine()` calls are retained as intentional test-body flushes, low-level SQL substrate cleanup, manual bucket-session cleanup, or dirty-worktree follow-up surfaces. They are not approved as generic fixture boilerplate.
- `src/aeat/entrypoints/cli/test_modelo_export_verb.py` remains a separate S93 follow-up candidate because prior migration exposed a real `project_answers` registration failure.
- `src/aeat/entrypoints/cli/test_repair_privacy_contract.py` remains a separate S93 follow-up candidate because a prior run surfaced diagnostics model-rebuild instability during migration.
- Auth-session tests containing `_Provider` test doubles were not migrated in this sweep and need separate test-quality classification under the no-fake/no-stub policy before fixture changes are made.

## Verdict

S93 migration is materially complete for normal profile-backed fixture setup, with approved explicit-route residuals inventoried above. S94 guard coverage now prevents new unapproved route-based test setup. S95 is complete when this audit is committed with the S94 guard evidence.
