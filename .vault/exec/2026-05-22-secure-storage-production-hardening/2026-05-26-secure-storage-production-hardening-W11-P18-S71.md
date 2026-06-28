---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S71'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-tr-locale-error-message-audit]]'
---



# `secure-storage-production-hardening` `W11.P18.S71`

Repaired secure-storage user-facing message surfaces so runtime readiness, active-session refusal, and SQL engine factory failures expose registry-backed translation keys.

## Changes

- Added translation keys to `StorageRuntimeReadinessIssue` and rendered readiness refusals through `errors.storage.runtime.not_ready`.
- Preserved existing diagnostic exception text for internal assertions while giving user-facing renderers a `translated_message` and structured `details` context.
- Converted `NoActiveBucketSessionError` to ignore legacy literal detail for user-facing rendering and use the existing no-active-session registry key.
- Converted the SQL engine empty-route and engine-creation failures to registry-backed storage translation keys.
- Generated locale key shape through `python -m aeat.locales scaffold`, then filled the secure-storage runtime and engine copy in every supported locale.

## Validation

- `uv run ruff check src\aeat\adapters\persistence\storage\runtime.py src\aeat\adapters\persistence\storage\master_key\_active_session.py src\aeat\adapters\persistence\storage\sql\engine.py src\aeat\adapters\persistence\storage\test_runtime.py src\aeat\adapters\persistence\storage\test_errors.py`
- `uv run pytest src\aeat\adapters\persistence\storage\test_runtime.py src\aeat\adapters\persistence\storage\test_errors.py src\aeat\adapters\persistence\storage\bucket\test_bucket_errors.py src\aeat\core\errors\test_registry_enforcement.py -q`
- `uv run python -m aeat.locales scaffold`
- `uv run python -m aeat.locales audit`
