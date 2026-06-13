---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S202]]'
---

# `secure-storage-production-hardening` `W12.P26.S202` Review

## S202-001 | PASS | Config reset remains bound to runtime storage routes

`reset_config()` resolves workflow state through `workflow_state_repository()`,
which binds to the active bucket runtime repository when an active profile exists
and uses the cold-bootstrap exception only for absent active-profile roots. The
PROFILE scope enumerates profile bucket manifests and deletes lifecycle records
through `UserProfileLifecycleRepository(bucket_id=profile_id)`, then disposes
cached SQL engines before removing each bucket directory. DATA scope delegates
unreadable-row quarantine to the diagnostics pipeline.

The S202 change adds `reset_config(..., confirmed=True)` calls for AUTH, PROFILE,
DATA, and ALL scopes to the runtime-default missing-session and
route/session-mismatch refusal matrices, so the service refuses before mutating
workflow state, scanning profile manifests, deleting bucket directories, or
quarantining secure-object rows when the active bucket storage session is absent
or mismatched.

## S202-002 | PASS | Unconfirmed reset error carries the registered locale key

`ConfigResetUnconfirmedError` already derives from the core `AeatError` hierarchy
and is registered as `REFUSED_CONFIG_RESET_UNCONFIRMED`. The raised error now
sets `translated_message="errors.refused.refused_config_reset_unconfirmed"` and
structured context containing the refused scope, without a raw English fallback
message. The application test resolves the message through the normal error
registry/i18n path, verifies it is not the placeholder key or old raw string,
and verifies the structured error envelope carries
`REFUSED_CONFIG_RESET_UNCONFIRMED`. The existing CLI wrapper continues to use
its CLI-specific `tr()` help/refusal surface before calling the service.

## S202-003 | PASS | Test shape remains real-behavior

The reset tests continue to use `isolated_profile_storage_root()` and
`profile_create_storage_span()` to exercise real secure SQL, profile lifecycle,
manifest scanning, and bucket removal behavior. The new runtime migration cases
call the production `reset_config()` service directly; no fakes, mocks, stubs,
monkeypatches, skips, xfails, or mirrored reset logic were introduced.

## S202-004 | PASS | Convention hygiene

No new exception classes, broad exception handlers, silent exception swallowing,
naked environment access, settings bypass, direct production
`SecureObjectRepository` construction, `noqa`, `pragma`, monkeypatch, fake,
mock, skip, xfail, or tautological test was introduced in the S202 code slice.
Locale catalogue edits were not required; the mandatory locale audit remains
clean.

Validation:

- `uv run --no-sync ruff check src/aeat/application/config_reset.py src/aeat/application/test_config_reset.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py` passed.
- `$env:PYTHONPATH='src'; uv run --no-sync -q pytest -q src/aeat/application/test_config_reset.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "config_reset"` passed with 14 selected tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Reviewer note: `vaultspec-code-reviewer` review returned one MEDIUM and one LOW
finding. The MEDIUM finding observed that the initial runtime gate covered only
AUTH and did not explicitly cover PROFILE, DATA, and ALL reset branches. That is
resolved by the final runtime matrix expansion. The LOW finding observed that
the first translation test asserted only literal-key storage. That is resolved by
the final registry/i18n rendering and error-envelope assertions.

Disposition: close `AFR-100`.
