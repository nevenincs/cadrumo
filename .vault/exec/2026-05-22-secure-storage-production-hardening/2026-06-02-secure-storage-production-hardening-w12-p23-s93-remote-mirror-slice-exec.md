---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S93'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` `W12.P23.S93` Remote Mirror Slice

## Description

- Migrate the remote-mirror test setup away from explicit database routes and injected SQL engines.
- Keep real encrypted secure-object rows, raw ciphertext manifest construction, and remote mirror adverse-condition assertions.

## Changed Surface

- `src/aeat/adapters/outbound/storage/test_mirror_manifest.py`
- `src/aeat/entrypoints/cli/_config/test_google_sync_push.py`

## Outcome

Closed for this slice.

The migrated tests now use `isolated_runtime_profile` and the runtime-owned secure-object repository. Manual `Settings(aeat_database_url=...)`, `create_engine_from_settings`, `Base.metadata.create_all`, `SecureObjectRepository(engine=...)`, and direct `EphemeralMasterKeyProvider` setup were removed from this slice.

The tests now use the registered `google_oauth_metadata` namespace definition for namespace and sensitivity while preserving opaque ciphertext, manifest hash, revision watermark, partial upload/download, stale mirror, revision conflict, and limit-refusal behavior.

## Verification

- `uv run --no-sync pytest -q src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/entrypoints/cli/_config/test_google_sync_push.py` - 19 passed.
- `uv run --no-sync ruff check src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/entrypoints/cli/_config/test_google_sync_push.py` - all checks passed.
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py` - 8 passed.
- `rg -n "AEAT_DATABASE_URL|aeat_database_url|Settings\\(|create_engine_from_settings|SecureObjectRepository\\(|EphemeralMasterKeyProvider|Base\\.metadata|monkeypatch|pytest\\.mark\\.skip|pytest\\.mark\\.xfail|_Fake|_Stub|patch\\(|unittest\\.mock" src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/entrypoints/cli/_config/test_google_sync_push.py -S` - no matches.
- `git diff --check -- src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/entrypoints/cli/_config/test_google_sync_push.py` - no whitespace errors.

## Notes

No HIGH or CRITICAL issue was identified in this slice.

S93 remains open because the row covers the broader `src/aeat` migration. Remaining scan hits include approved low-level SQL/route tests and other unreviewed residual slices outside the remote-mirror test setup repaired here.
