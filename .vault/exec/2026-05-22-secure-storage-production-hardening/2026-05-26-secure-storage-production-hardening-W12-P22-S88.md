---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S88'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-production-hardening-w12-p22-s88-review-audit]]'
---



# `secure-storage-production-hardening` `W12.P22.S88`

Moved CLI guarded profile-bound write route decisions behind an application runtime write-policy query while preserving bootstrap exemptions.

## Changes

- Added a typed storage write-policy backend with a frozen decision model, machine-readable outcome codes, and the canonical profile-bound write verb catalogue.
- Reduced the CLI root callback to collect the operator verb path, pass bootstrap-exemption state into the backend policy query, and raise the existing `CliRefusedBoundaryError` from the returned translated refusal message.
- Removed CLI-local route classification, explicit route-kind branching, and the root-fallback guarded verb table from the CLI root module.
- Preserved bootstrap exemptions as strictly sessionless at the root boundary; after review remediation, exempt verbs return before root session activation and no broad suppression hides activation failures.
- Removed stale `cli.config.init.*` locale catalogue blocks from the maintained en/es/ca catalogues. Source scans under `src/aeat` now find deprecated `config init` only in the explicit regression-test assertion that the command remains absent.
- Added focused backend-policy tests for root fallback refusal, explicit database URL refusal, active bucket allowance, bootstrap exemption short-circuiting, and read/recovery path allowance.
- Updated CLI real-entrypoint tests to prove the root delegates route classification to the backend policy and still refuses root fallback/explicit database routes before write verbs can create database files.

## Validation

- `uv run --no-sync ruff check src/aeat/application/storage_write_policy.py src/aeat/application/test_storage_write_policy.py src/aeat/entrypoints/cli/__init__.py src/aeat/entrypoints/cli/test_root_fallback_write_guard.py` - passed.
- `uv run --no-sync pytest src/aeat/application/test_storage_write_policy.py src/aeat/entrypoints/cli/test_root_fallback_write_guard.py src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py -q` - 59 passed.
- `uv run --no-sync pytest src/aeat/application/test_storage_write_policy.py src/aeat/entrypoints/cli/test_root_fallback_write_guard.py src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py src/aeat/entrypoints/cli/test_cold_start_no_profile.py src/aeat/entrypoints/cli/test_fast_path_no_state.py src/aeat/adapters/persistence/storage/test_runtime.py -q` - 88 passed.
- `rg -n "contextlib\\.suppress|suppress\\(Exception\\)|with suppress\\(Exception\\)|ctx\\.with_resource\\(get_master_key_provider\\(\\)\\)" src/aeat/entrypoints/cli/__init__.py src/aeat/entrypoints/cli/_config/__init__.py src/aeat/application/wizard/_commands.py` - only the non-exempt root session activation remains.
- `rg -n "cli\\.config\\.init|aeat config init|config init" src/aeat/application/storage_write_policy.py src/aeat/application/test_storage_write_policy.py src/aeat/entrypoints/cli/__init__.py src/aeat/entrypoints/cli/test_root_fallback_write_guard.py src/aeat/locales/en.yml src/aeat/locales/es.yml src/aeat/locales/ca.yml` - no matches.
- `uv run --no-sync python -m aeat.locales audit` - still fails on pre-existing `hu.yml` parity debt, but the deprecated `cli.config.init.*` entries are no longer reported.

## Review

The mandatory code review initially found `S88-001`, a medium issue where bootstrap-exempt verbs still attempted root session activation under broad exception suppression. The remediation removed that path, and the narrow re-review passed.

## Follow-Up

The broader custody/profile-create gate still exposes a profile lifecycle failure where wizard-backed profile creation opens the master-key provider before provisioning custody. That is tracked to `W12.P22.S89`, whose row explicitly moves profile create/switch/delete/logout storage spans behind named runtime or profile-lifecycle operations.
