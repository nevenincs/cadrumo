---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S74'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-settings-env-audit]]'
---



# `secure-storage-production-hardening` `W11.P19.S74`

Repaired settings-backed route derivation and updated a profile-health test slice away from explicit database URLs.

## Changes

- Updated `override_settings()` so changing the storage root or active profile re-runs database-route derivation when the operator did not explicitly set `aeat_database_url`.
- Adopted the current centralized storage-route classifier definitions so runtime guards can distinguish explicit database URLs, active bucket databases, and root fallback databases.
- Reworked profile-health tests to use `override_settings()` with storage root / active profile state, pointer-file routing, and real active `BucketSession` contexts instead of explicit SQLite URLs.
- Preserved explicit database URL semantics: when `aeat_database_url` is explicitly set, it remains an explicit route and is not silently converted into a bucket route.

## Validation

- `uv run ruff check src\aeat\core\config.py src\aeat\application\workflow\test_profile_health.py`
- `uv run pytest src\aeat\application\workflow\test_profile_health.py src\aeat\core\test_storage_route_classification.py src\aeat\tests\test_config.py -q`
- `uv run pytest src\aeat\adapters\persistence\storage\test_runtime.py src\aeat\application\test_state_projection.py src\aeat\application\workflow\test_profile_health.py src\aeat\application\workflow\test_profile_bucket_scan.py src\aeat\core\test_storage_route_classification.py src\aeat\tests\test_config.py -q`
