---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S203]]'
---

# `secure-storage-production-hardening` `W12.P26.S203` Review

## S203-001 | PASS | Diagnostics secure-object probe uses runtime storage and logs degradation

`secure_object_unreadable_total()` delegates to the diagnostics secure-object
integrity probe, which resolves storage through
`secure_object_repository_for_active_bucket_or_default_route()`. With an active
profile selected, route/session failures surface from the active bucket runtime
rather than falling back to a bare repository. The diagnostics probe catches that
runtime failure only to produce an empty diagnostic aggregate, and logs the
failure at debug level with exception info.

## S203-002 | PASS | Missing-session and route-mismatch behavior is now pinned

`test_diagnostics.py` now covers both missing active bucket session and
active-session route mismatch for `secure_object_unreadable_total()`. Both tests
use real settings overrides and real `BucketSession` objects, assert the
diagnostics aggregate is empty, and assert the debug log records the storage
runtime failure type and route-specific detail. `test_runtime_migrated_repositories.py`
also carries explicit diagnostics degradation cases beside the runtime refusal
matrix, so S203 is visible in the migrated-runtime gate without forcing
degradation surfaces into a raises-only contract.

The repair quarantine paths are intentionally different: they use
`active_bucket_repair_session()` so `aeat config repair quarantine` can open a
repair session for bootstrap-adjacent recovery. Existing tests already cover
that bootstrap-exempt behavior for preview and mutation paths.

## S203-003 | PASS | Existing active-profile isolation coverage remains in place

`test_runtime_migrated_repositories.py` already verifies diagnostics-side
secure-object probing remains profile-local: a diagnostic probe row written under
bucket A is invisible under bucket B, and bucket A later reports the expected
namespace. The S203 change does not alter production diagnostics code.

## S203-004 | PASS | Privacy and plain-file boundaries are explicit

Repair diagnostics redact active profile identifiers through
`CLI_PROFILE_ID_PLACEHOLDER`. The retained plain-file surface is diagnostic log
path reporting via `default_log_file_path()` and does not mutate secure storage
or expose decrypted payloads.

## S203-005 | PASS | Convention hygiene

No production code changed. No new exception classes, broad exception handlers,
silent exception swallowing, naked environment access, settings bypass, direct
production `SecureObjectRepository` construction, raw user-facing strings,
`noqa`, `pragma`, monkeypatch, fake, mock, skip, xfail, or tautological test was
introduced in the S203 slice.

Validation:

- `uv run --no-sync ruff check src/aeat/application/diagnostics.py src/aeat/application/test_diagnostics.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py` passed.
- `uv run --no-sync pytest src/aeat/application/test_diagnostics.py -k "secure_object_unreadable_total or quarantine" -q` passed with 8 selected tests.
- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "diagnostic or auth_diagnostics or s85_runtime" -q` passed with 5 selected tests.
- Prior committed S203 host validation also recorded
  `$env:PYTHONPATH='src'; uv run --no-sync -q pytest -q src/aeat/application/test_diagnostics.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "auth_diagnostics or secure_objects or diagnostics or migrated_runtime_defaults_refuse"` passing with 115 selected tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Reviewer note: `vaultspec-code-reviewer` review returned one HIGH, one MEDIUM,
and two LOW findings. The HIGH finding observed that the plan had S203 checked
while AFR-101 remained pending; the final plan diff closes AFR-101 and aligns
S204/S205 with their recorded closures. The MEDIUM finding requested
migrated-runtime coverage for the diagnostics surface; the final runtime
migration file now includes explicit missing-session and route-mismatch
diagnostics degradation cases. The LOW finding on shallow debug-log assertions
is resolved by asserting route-specific message fragments. The LOW plan-scope
finding is resolved by removing the generated LINK RULES block from the plan
diff before commit.

Disposition: close `AFR-101`.
