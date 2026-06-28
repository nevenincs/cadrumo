---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S51'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` `W07.P12.S51`

## Description

- Select the next application or CLI secure-SQL hygiene slice from the S50 inventory.
- Check runtime-readiness implications before selecting a repair target, including package autouse fixtures, central secure-SQL helpers, and bespoke storage setup.
- Defer code repair to the later repair rows; this step records the selected bounded target.

## Outcome

Closed.

Selected next application hygiene slice: the `src/aeat/application/modelo` bespoke storage-fixture cluster, starting with `test_export.py` and `test_reconcile.py`.

Rationale:

- `src/aeat/application/filing/*` raw constructor hits are already isolated by `src/aeat/application/filing/conftest.py`, which uses autouse `isolated_runtime_profile(..., bucket_id="filing-test")`.
- `src/aeat/application/user_profile/test_profile_repository.py` uses autouse `isolated_profile_storage_root`, which is the correct profile-bootstrap helper because those tests create profiles rather than consume an already-active runtime profile.
- `src/aeat/application/modelo/test_export.py` and `src/aeat/application/modelo/test_reconcile.py` use bespoke `override_settings(aeat_local_storage_root=..., aeat_secret_store_backend=file, aeat_secret_passphrase=dev_test_database_password())` plus `profile_create_storage_span(...)`, then instantiate runtime-default repositories. This is real behavior, but it duplicates runtime setup rather than using the central helper surface.
- CLI files with default constructors are downstream of the same model/work-unit runtime pattern. They should not be repaired first until the application pattern is validated.

S52 validation target:

- Prove whether the `application/modelo` tests can move to `isolated_profile_storage_root` or `isolated_cli_runtime_profile` without losing the behavior under test.
- Preserve active-profile/session refusal tests that intentionally assert runtime-not-ready paths.
- Keep all repository construction real; do not replace with fakes, stubs, mocks, monkeypatch, skip, or xfail.

Verification:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py` -> 2 passed.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py` -> all checks passed.

## Notes

No HIGH or CRITICAL issue was identified in this selection step.
