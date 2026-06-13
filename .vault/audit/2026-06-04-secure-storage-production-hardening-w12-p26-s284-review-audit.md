---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Code Review

## S284-001 | PASS | Manifest discovery boundary

`_profile_bucket_scan.py` is a plaintext manifest scanner. It uses bucket layout
and manifest helpers to resolve UUIDs and labels, and does not import or call
encrypted storage runtime, session, master-key, SQL, or remote-provider APIs.

## S284-002 | PASS | Data consistency and lifecycle filtering

Live-surface discovery excludes tombstoned profiles by default, while UUID-direct
lookup can still inspect a tombstoned profile for diagnostics. Ambiguous labels
raise `ProfileLabelAmbiguousError` instead of picking a bucket silently.

## S284-003 | PASS | Exception observability

Malformed manifests and invalid bucket directory names are not silently swallowed:
the live scanner logs debug skip messages, and the separate scan-issue API returns
structured `ProfileBucketScanIssue` rows for repair/audit surfaces.

## S284-004 | PASS | Tests and localization

The focused tests are filesystem-real and cover malformed manifest handling,
active-profile resolution, label fallback, and ambiguity. No locale work was
required because the module has no user-facing render strings.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/workflow/_profile_bucket_scan.py src/aeat/application/workflow/test_profile_bucket_scan.py src/aeat/application/workflow/test_active_profile_resolution.py`
- `uv run --no-sync pytest -q src/aeat/application/workflow/test_profile_bucket_scan.py src/aeat/application/workflow/test_active_profile_resolution.py`
- `uv run --no-sync -q python -m aeat.locales audit`
