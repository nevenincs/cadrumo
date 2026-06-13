---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S284'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S284 - Close AFR-182 for profile bucket scan

Scope: close `AFR-182` for `src/aeat/application/workflow/_profile_bucket_scan.py`
with signals `manifest-bucket, plain-file`, target `manifest-discovery`, and
owner `W12.P22.S90`.

## Description

- Audited profile-bucket manifest discovery and live/tombstoned filtering.
- Confirmed the module reads plaintext manifests only and does not open encrypted
  storage, runtime repositories, active sessions, master-key providers, SQL, or
  remote providers.
- Verified malformed manifests are skipped with debug logging and are also exposed
  through `list_profile_bucket_scan_issues()`.
- Confirmed profile label ambiguity raises the typed AEAT workflow error.
- Closed `W12.P26.S284` through `vaultspec-core vault plan step check` and
  updated the `AFR-182` register status to `closed`.

## Outcome

`AFR-182` is closed as the canonical plaintext manifest-discovery adapter for
profile bucket pointers. No production code change was required in this step.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/workflow/_profile_bucket_scan.py src/aeat/application/workflow/test_profile_bucket_scan.py src/aeat/application/workflow/test_active_profile_resolution.py`
- `uv run --no-sync pytest -q src/aeat/application/workflow/test_profile_bucket_scan.py src/aeat/application/workflow/test_active_profile_resolution.py`
- `uv run --no-sync -q python -m aeat.locales audit`

## Notes

The scanner remains intentionally plaintext and read-only. Its role is discovery
and readiness classification, not secure-object payload access.
