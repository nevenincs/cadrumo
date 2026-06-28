---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S426'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-w05-p10-s43-review-audit]]'
---

# `secure-storage-production-hardening` `W05.P10.S426`

## Description

- Preflight existing remote mirror manifests before object writes.
- Block remote revision conflicts before overwriting mirrored ciphertext.
- Record repairable partial upload, partial download, and stale mirror states as degraded manifest entries.
- Reject non-dry-run limited pushes because they cannot produce complete namespace manifests.
- Post-inspect uploaded manifests before counting them as pushed.
- Extend the `config.google.sync.push` JSON payload with degraded manifest counts and details.

## Outcome

`W05.P10.S426` is complete. The operator sync push path now invokes the mirror inspection contract through the production helper and surfaces partial upload, partial download, stale mirror, and revision conflict states without relying on test-only providers.

Validation:

- `uv run --no-sync ruff check src/aeat/adapters/outbound/storage/_records.py src/aeat/adapters/outbound/storage/_mirror_manifest.py src/aeat/adapters/outbound/storage/__init__.py src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/adapters/outbound/storage/test_foundation.py src/aeat/adapters/outbound/storage/test_google_drive_live.py src/aeat/entrypoints/cli/_config/_google.py src/aeat/entrypoints/cli/_config/_google_payloads.py src/aeat/entrypoints/cli/_config/test_google_sync_push.py`
- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/_config/test_google_sync_push.py` passed with 6 tests.
- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/test_json_schema_conformance.py` passed with 190 tests.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/adapters/outbound/storage/test_foundation.py src/aeat/entrypoints/cli/_config/test_google_sync_push.py src/aeat/entrypoints/cli/test_json_schema_conformance.py` passed with 218 tests.

## Notes

The sync-push payload schema change is covered by the JSON schema conformance gate.
