---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
step_id: 'S73'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-exception-observability-audit]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline `code`. -->

# `secure-storage-production-hardening` `W11.P18.S73`

Repaired secure-storage-adjacent silent exception handling so degraded reads are observable.

## Changes

- Added debug logging when active-profile label resolution suppresses manifest/path errors.
- Added typed profile-bucket scan issue records and debug logging for unreadable manifests skipped from live profile listings.
- Added debug logging when calculation result summaries degrade because the work unit or registry snapshot cannot be resolved.
- Hardened the bucket-session cleanup observability repair so import/setup defects still surface, while runtime engine eviction failures during `close()` log at warning level instead of disappearing.
- Kept the bucket-session cleanup log privacy-preserving by recording only the exception type, with no bucket id, filesystem path, URL, traceback, key material, `noqa`, or coverage pragma.
- Fixed nested runtime-readiness detail rendering to use the settings-level output language, preventing profile-language recursion while preserving localized rendering.
- Added a real-behavior malformed-manifest test that verifies the live profile surface stays empty while the scan issue surface and debug log record the failure.

## Deferred

- The low-priority modelo CLI period-hint fallback remains deferred because that file contains unrelated in-flight CLI edits outside this secure-storage observability slice.
- Existing profile-health tests still need S74 settings-backed active-bucket repair; the S73 gate avoided closing that separate failure under this step.

## Validation

- `uv run ruff check src\aeat\adapters\persistence\storage\runtime.py src\aeat\application\state_projection.py src\aeat\application\workflow\_profile_bucket_scan.py src\aeat\application\workflow\test_profile_bucket_scan.py src\aeat\application\modelo\_result_summary.py src\aeat\adapters\persistence\storage\master_key\_bucket_session.py`
- `uv run pytest src\aeat\adapters\persistence\storage\test_runtime.py src\aeat\application\test_state_projection.py src\aeat\application\workflow\test_profile_bucket_scan.py src\aeat\adapters\persistence\storage\master_key\test_idle_timeout.py -q`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/master_key/_bucket_session.py src/aeat/core/errors/registry/_domain.py`
- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/master_key/test_bucket_session.py src/aeat/adapters/persistence/storage/master_key/test_master_key.py src/aeat/core/errors/test_registry_enforcement.py -q`
- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/test_runtime.py src/aeat/application/test_state_projection.py -q`

## Review

The final targeted review found no issues. The reviewer confirmed that the local imports remain outside the cleanup `try`, that the catch boundary only covers runtime cleanup, that the warning log does not leak bucket ids, local paths, URLs, or key material, and that the patch added no `noqa`, pragma, or deprecated CLI/config surface.
