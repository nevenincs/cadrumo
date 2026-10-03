---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-10-03'
body_hash: 'sha256:32f8c9c4cc73919cd9a638e32206f2e1acd46a7e209826fef3c8f744c2a9251e'
related: []
---

# `secure-storage-production-hardening` `W12.P23.S95` Test-Isolation Closeout

## Scope

This audit closes the S93-S95 test-isolation sweep for explicit database-route setup. S93 migrated repeated fixture-level custody setup to centralized runtime helpers where the tests were exercising normal profile-backed behavior. S94 now rejects new unapproved executable `aeat_database_url` / `AEAT_DATABASE_URL` setup outside the approved inventory below.

## Approved Residual Categories

### Low-level SQL and envelope substrate

These files intentionally construct explicit SQLite routes because their subject is the SQL engine, encrypted-object repository substrate, archive-bundle behavior, constraint behavior, or secure-bound adapter contract:

- the retired test
- the retired test
- the retired test
- the retired test
- the retired test
- the retired test
- the retired module
- the retired test
- the retired test

Owning behavior: low-level substrate tests prove encrypted SQL persistence and repository semantics without routing through the profile runtime. These remain approved because they are below the runtime policy boundary.

### Runtime route classification and guard policy

These files intentionally use explicit routes because their subject is route classification, runtime refusal, route precedence, or the guard itself:

- the retired test
- the retired test
- the retired test
- the retired test

Owning behavior: these tests assert the centralized settings/runtime route rules. They are the approved place to describe or exercise explicit route handling directly.

### Application and CLI refusal contracts

These files intentionally retain explicit-route setup because they assert that higher-level application or CLI boundaries refuse explicit database routing, preserve cold-start behavior, or avoid leaking raw internal errors:

- the retired test
- the retired test
- the retired test
- the retired test
- the retired test
- the retired test
- the retired test
- the retired test
- the retired test

Owning behavior: these tests pin refusal, diagnostics, repair, and cold-start contracts. They remain approved only insofar as they test explicit-route refusal/classification or raw-error non-leak behavior.

### Shared settings and test-helper boundary

These files intentionally retain explicit-route references because they test or implement the centralized settings/test helper boundary itself:

- the retired test
- the retired test
- the retired test

Owning behavior: `secure_sql.py` is the sanctioned helper layer for low-level explicit SQL isolation and runtime profile setup. `test_secure_sql.py` and `test_config.py` assert the settings/helper behavior and explicit route precedence contracts.

## Guard Contract

the retired test now scans executable test and shared test-helper sources for `aeat_database_url`, `AEAT_DATABASE_URL`, and embedded executable string constants. Any new executable hit outside the approved inventory fails the guard. Docstring-only narrative mentions are ignored so tests can describe the route policy without becoming false positives.

## Remaining Follow-Up

- The guard is file-level, not call-site-level. Additional explicit-route setup inside an approved file will not fail the guard automatically; maintainers must keep those files within the owning behavior above.
- Several remaining `dispose_engine()` calls are retained as intentional test-body flushes, low-level SQL substrate cleanup, manual bucket-session cleanup, or dirty-worktree follow-up surfaces. They are not approved as generic fixture boilerplate.
- the retired test remains a separate S93 follow-up candidate because prior migration exposed a real `project_answers` registration failure.
- the retired test remains a separate S93 follow-up candidate because a prior run surfaced diagnostics model-rebuild instability during migration.
- Auth-session tests containing `_Provider` test doubles were not migrated in this sweep and need separate test-quality classification under the no-fake/no-stub policy before fixture changes are made.

## Verdict

S93 migration is materially complete for normal profile-backed fixture setup, with approved explicit-route residuals inventoried above. S94 guard coverage now prevents new unapproved route-based test setup. S95 is complete when this audit is committed with the S94 guard evidence.
