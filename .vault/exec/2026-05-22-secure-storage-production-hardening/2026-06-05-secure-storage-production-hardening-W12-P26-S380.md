---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S380'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S380 - Close AFR-278 for profile censo bootstrap custody

Scope: close `AFR-278` for `src/aeat/entrypoints/cli/_config/_profile_censo.py`
with signals `active-profile, manifest-bucket`, target `bootstrap-custody`, and
owner `W12.P22.S89`.

## Description

- Re-grounded the stale plan row from retired `_profile_census.py` wording to the
  current `_profile_censo.py` command surface.
- Audited `aeat config profile censo` as a thin CLI layer over `CensoSyncService`,
  active-profile resolution, manifest lookup, censo snapshot persistence, and bucket
  event emission.
- Confirmed censo snapshot and profile writes remain in application services using
  bucket-scoped repositories; the CLI does not reimplement censo modelo foundation
  routing or open raw storage routes.
- Bound censo bucket-event persistence to
  `secure_object_repository_for_bucket(bucket_id)` instead of constructing
  `BucketEventHistoryRepository` through the ambient active-bucket default.
- Corrected `_active_pointer()` return typing from operator profile-name labels to
  core `BucketId`, matching the manifest-scanner and secure-storage boundary.
- Closed `W12.P26.S380` through `vaultspec-core vault plan step check` and updated
  the `AFR-278` register status to `closed`.

## Outcome

`AFR-278` is closed as `bootstrap-custody`. The profile censo CLI remains an intended
profile lifecycle surface: it resolves the active bucket through the centralized
active-profile pointer, verifies the manifest by id, delegates persisted censo/profile
state to application services, and now writes censo bucket events through an explicit
bucket-bound secure-object repository.

Validation passed:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_config/_profile_censo.py src/aeat/entrypoints/cli/_config/_profile_censo_payloads.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py`
- `uv run --no-sync -q python -m aeat.locales audit`

## Notes

The explorer agent pool was at its thread limit during this slice, so the S380 review
was performed locally. No locale leaves were added in this step.
