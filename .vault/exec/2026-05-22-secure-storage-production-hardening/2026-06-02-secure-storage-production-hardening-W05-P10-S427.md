---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S427'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-w05-p10-s43-review-audit]]'
---

# `secure-storage-production-hardening` `W05.P10.S427`

## Description

- Removed timestamp-only stale fallback from remote manifest comparison.
- Kept `STALE_MIRROR` limited to the immediate predecessor revision that the manifest can prove.
- Classified older root revisions and older naive-timestamp revisions as `REVISION_CONFLICT`.
- Wrapped malformed remote manifest JSON in `OutboundStorageIntegrityError`.
- Added real-behavior tests using `SecureObjectRepository` and `LocalFileSystemProvider`.

## Outcome

`W05.P10.S427` is complete. The mirror comparator no longer misclassifies divergent older root revisions as stale, and malformed manifests stay inside the existing AEAT outbound-storage exception hierarchy.

Validation:

- `uv run --no-sync ruff check src/aeat/adapters/outbound/storage/_records.py src/aeat/adapters/outbound/storage/_mirror_manifest.py src/aeat/adapters/outbound/storage/__init__.py src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/adapters/outbound/storage/test_foundation.py src/aeat/adapters/outbound/storage/test_google_drive_live.py src/aeat/entrypoints/cli/_config/_google.py src/aeat/entrypoints/cli/_config/_google_payloads.py src/aeat/entrypoints/cli/_config/test_google_sync_push.py`
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/adapters/outbound/storage/test_foundation.py` passed with 22 tests.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/adapters/outbound/storage/test_foundation.py src/aeat/entrypoints/cli/_config/test_google_sync_push.py src/aeat/entrypoints/cli/test_json_schema_conformance.py` passed with 218 tests.

## Notes

The accepted rule is intentionally conservative. Deep stale recovery is not inferred from timestamps; future recovery would require deeper lineage evidence in the manifest contract.
