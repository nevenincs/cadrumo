---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S439'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-w05-p10-s43-review-audit]]'
---

# `secure-storage-production-hardening` `W06.P11.S439`

## Description

- Tightened remote mirror provider comparison so upload and download inspection verify returned provider metadata as well as payload bytes.
- `_provider_payload_matches_manifest_entry` now checks namespace, object HMAC, provider byte length, payload length, provider hash, and actual payload SHA-256 against the manifest entry.
- Added real-behavior metadata drift tests by corrupting the `LocalFileSystemProvider` sidecar byte length while keeping the encrypted payload and content hash aligned with the manifest.

## Outcome

Closed.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/adapters/outbound/storage/test_foundation.py` passed with 24 tests.
- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/_config/test_google_sync_push.py` passed with 6 tests.
- `uv run --no-sync ruff check src/aeat/adapters/outbound/storage/_mirror_manifest.py src/aeat/adapters/outbound/storage/test_mirror_manifest.py` passed.
