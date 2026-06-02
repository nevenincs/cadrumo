---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
step_id: 'S43'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-W05-P10-S43-review]]'
---

# `secure-storage-production-hardening` `W05.P10.S43`

Detected remote mirror partial upload, partial download, stale mirror, and
revision conflict states against encrypted object manifests.

## Description

- Added typed remote mirror inspection issue records and issue kinds.
- Added upload inspection that compares expected manifests, remote manifests,
  fetched ciphertext bytes, and provider metadata.
- Added download inspection that rejects missing, corrupt, or manifest-drifting
  ciphertext objects.
- Added manifest comparison that distinguishes absent entries, stale mirrors,
  incompatible revisions, and ciphertext hash conflicts.
- Hardened stale detection for multi-revision lag, mixed naive and aware
  timestamps, and explicit divergent lineage evidence.
- Added real-behavior storage tests using `SecureObjectRepository`,
  `EphemeralMasterKeyProvider`, SQLite, and `LocalFileSystemProvider`.

## Outcome

`W05.P10.S43` now exposes `RemoteMirrorInspection` results for remote mirror
degradation and has focused real-behavior coverage for partial upload, partial
download, ciphertext drift, immediate stale mirrors, older stale mirrors,
timestamp normalization, and revision conflicts.

Modified files:

- `src/aeat/adapters/outbound/storage/_records.py`
- `src/aeat/adapters/outbound/storage/_mirror_manifest.py`
- `src/aeat/adapters/outbound/storage/__init__.py`
- `src/aeat/adapters/outbound/storage/test_mirror_manifest.py`

Review audit:

- `2026-06-02-secure-storage-production-hardening-W05-P10-S43-review`

Validation:

- `uv run --no-sync ruff check src/aeat/adapters/outbound/storage/_records.py src/aeat/adapters/outbound/storage/_mirror_manifest.py src/aeat/adapters/outbound/storage/__init__.py src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/adapters/outbound/storage/test_foundation.py`
- `uv run --no-sync pytest src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/adapters/outbound/storage/test_foundation.py -q`
- `git diff --check -- src/aeat/adapters/outbound/storage/_records.py src/aeat/adapters/outbound/storage/_mirror_manifest.py src/aeat/adapters/outbound/storage/__init__.py src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/adapters/outbound/storage/test_foundation.py .vault/audit/2026-06-02-secure-storage-production-hardening-W05-P10-S43-review.md`

## Notes

Mandatory review found no HIGH or CRITICAL findings. Initial MEDIUM findings
for download drift and older stale mirrors were resolved before closure. A
follow-up MEDIUM for timestamp-only stale classification was resolved by
normalizing timestamps and refusing timestamp fallback when explicit previous
revision lineage conflicts.

One LOW lineage-depth residual remains in the audit: current manifest entries
carry one-hop previous revision metadata, so an older remote root revision with
no incompatible previous revision id cannot be proven ancestor versus divergent
without future manifest lineage expansion.
