---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S409'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` `W15.P32.S409`

Added and repaired guard coverage against direct passphrase-env imports and unapproved default secure-object repository construction.

- Modified: `src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py`
- Modified: `src/aeat/adapters/persistence/storage/runtime_repository.py`
- Modified: `src/aeat/adapters/persistence/storage/envelope/_secure_repository.py`

## Description

The hardening guard now matches the current storage architecture: runtime-owned factories may construct `SecureObjectRepository`, helper test-suite modules are recognized as tests, and bucket-session cleanup is required to log failures at debug-or-warning level instead of silently swallowing them.

Runtime repository helpers now bind explicit engines for process-default routes. Secure-bound envelope repositories resolve storage through the runtime helper so active-bucket route/session failures surface instead of being hidden by a bare repository fallback.

Code review found that bootstrap-exempt repair list/quarantine paths could still resolve an active-bucket repository without opening a session. That was fixed by routing repair list and diagnostics quarantine through the active-bucket repair session helper before repository resolution.

## Tests

Passed:

- `uv run pytest -q src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py src/aeat/application/test_repair_integrity.py src/aeat/application/test_diagnostics.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py src/aeat/entrypoints/cli/test_repair_policy_coverage.py`
- `uv run pytest -q src/aeat/application/test_repair_integrity.py::TestBuildListReport::test_list_opens_active_bucket_session_for_bootstrap_exempt_repair src/aeat/application/test_diagnostics.py::test_quarantine_preview_opens_session_for_bootstrap_exempt_repair src/aeat/application/test_diagnostics.py::test_quarantine_opens_session_for_bootstrap_exempt_repair`
- `uv run ruff check src/aeat/adapters/persistence/storage/runtime.py src/aeat/adapters/persistence/storage/runtime_repository.py src/aeat/adapters/persistence/storage/envelope/_secure_repository.py src/aeat/application/repair_integrity.py src/aeat/application/diagnostics.py src/aeat/application/test_repair_integrity.py src/aeat/application/test_diagnostics.py src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`
