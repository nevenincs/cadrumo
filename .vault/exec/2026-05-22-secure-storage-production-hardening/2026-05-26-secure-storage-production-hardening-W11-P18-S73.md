---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S73'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-exception-observability-audit]]'
---



# `secure-storage-production-hardening` `W11.P18.S73`

Repaired secure-storage-adjacent silent exception handling so degraded reads are observable.

## Changes

- Added debug logging when active-profile label resolution suppresses manifest/path errors.
- Added typed profile-bucket scan issue records and debug logging for unreadable manifests skipped from live profile listings.
- Added debug logging when calculation result summaries degrade because the work unit or registry snapshot cannot be resolved.
- Adopted the in-flight bucket-session cleanup observability repair so engine eviction failures during `close()` log at debug level instead of disappearing.
- Fixed nested runtime-readiness detail rendering to use the settings-level output language, preventing profile-language recursion while preserving localized rendering.
- Added a real-behavior malformed-manifest test that verifies the live profile surface stays empty while the scan issue surface and debug log record the failure.

## Deferred

- The low-priority modelo CLI period-hint fallback remains deferred because that file contains unrelated in-flight CLI edits outside this secure-storage observability slice.
- Existing profile-health tests still need S74 settings-backed active-bucket repair; the S73 gate avoided closing that separate failure under this step.

## Validation

- `uv run ruff check src\aeat\adapters\persistence\storage\runtime.py src\aeat\application\state_projection.py src\aeat\application\workflow\_profile_bucket_scan.py src\aeat\application\workflow\test_profile_bucket_scan.py src\aeat\application\modelo\_result_summary.py src\aeat\adapters\persistence\storage\master_key\_bucket_session.py`
- `uv run pytest src\aeat\adapters\persistence\storage\test_runtime.py src\aeat\application\test_state_projection.py src\aeat\application\workflow\test_profile_bucket_scan.py src\aeat\adapters\persistence\storage\master_key\test_idle_timeout.py -q`
