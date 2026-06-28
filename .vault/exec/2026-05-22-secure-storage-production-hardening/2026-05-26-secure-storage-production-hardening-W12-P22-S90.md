---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S90'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-production-hardening-w12-p22-s90-review-audit]]'
---



# `secure-storage-production-hardening` `W12.P22.S90`

Preserved plaintext manifest scanning as a read-only profile discovery adapter and hardened adjacent user-profile repository tests so encrypted runtime attachment is exercised through active bucket sessions.

## Changes

- Added an AST/source boundary test proving `_profile_bucket_scan` does not import or reference encrypted runtime/session attachment APIs such as master-key provider activation, runtime repository construction, workflow state loading, or user-profile secure repositories.
- Kept the malformed-manifest scanner test as real behavior coverage: unreadable manifests are skipped from the live surface and reported through scan issues with debug logging.
- Migrated user-profile lifecycle and snapshot repository tests away from direct secure-object repository injection, explicit engine construction, and manual metadata setup.
- Added a small manifest-backed active-profile storage helper so default repository tests construct storage through `_secure_objects_for_bucket` and runtime route attachment.
- Removed fallback bucket session activation from the reviewed repository tests. Active sessions now resolve through the active-profile settings chain.
- Kept explicit primary database URL coverage only as a fail-closed runtime refusal test, not as repository setup.

## Validation

- `uv run --no-sync ruff check src/aeat/application/workflow/test_profile_bucket_scan.py src/aeat/application/workflow/_profile_bucket_scan.py src/aeat/application/user_profile/test_repository.py src/aeat/application/user_profile/test_profile_repository.py` - passed.
- `uv run --no-sync pytest src/aeat/application/workflow/test_profile_bucket_scan.py src/aeat/application/user_profile/test_repository.py src/aeat/application/user_profile/test_profile_repository.py -q` - 27 passed.
- `rg -n "SecureObjectRepository|create_engine_from_settings|Base\\.metadata|activate_master_key_provider|fallback_bucket_id|objects=" src/aeat/application/user_profile/test_repository.py` - no matches.

## Review

Initial review found high-severity test architecture drift: direct secure-object injection and fallback bucket sessions still bypassed the hardened runtime. Remediation moved the tests onto manifest-backed active-profile sessions and default repository construction. Narrow re-review passed with no high or critical findings.
