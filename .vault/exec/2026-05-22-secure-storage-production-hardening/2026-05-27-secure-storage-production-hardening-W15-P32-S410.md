---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S410'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` `W15.P32.S410`

Regrounded storage-facing tests on centralized settings isolation instead of naked default repository state.

- Modified: `src/aeat/application/test_repair_integrity.py`
- Modified: `src/aeat/application/test_diagnostics.py`

## Description

The repair integrity tests now carry an autouse `override_settings(aeat_database_url=...)` isolation fixture with engine disposal before and after each test. Direct report builders receive injected real `SecureObjectRepository` instances so the application tests do not depend on active-profile runtime state.

The diagnostics tests now isolate `aeat_local_storage_root` by default and keep explicit database routes only inside tests that intentionally exercise explicit SQL behavior. This preserves active-profile tests that use `isolated_runtime_profile` while satisfying the secure SQL isolation guard.

The repair privacy CLI tests now write and inspect rows through `secure_object_repository_for_active_bucket()` so they exercise the same active-bucket route used by the repair CLI instead of the process-default repository.

Direct application tests now clear the active-session context before invoking repair list, quarantine preview, and quarantine mutation so the bootstrap-exempt repair session path is covered without relying on the in-process CLI runner.

## Tests

Passed:

- `uv run pytest -q src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py src/aeat/application/test_repair_integrity.py src/aeat/application/test_diagnostics.py`
- `uv run pytest -q src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py src/aeat/application/test_repair_integrity.py src/aeat/application/test_diagnostics.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py src/aeat/entrypoints/cli/test_repair_policy_coverage.py`
