---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening-W05-P10-S43` Code Review

No HIGH or CRITICAL findings were identified.

## S43-001 | MEDIUM | Download inspection accepts ciphertext that does not match the manifest

`inspect_remote_mirror_download` calls `provider.get` for each manifest object but ignores the returned payload and `ProviderObjectMetadata`. A provider object can therefore be readable and internally self-consistent while carrying a different byte length and ciphertext hash than the `RemoteMirrorObjectManifest` entry, and the inspection still returns `ok=True`. This misses a partial or corrupted download where the manifest names ciphertext revision metadata that is not actually retrievable from the provider. The real-behavior test only covers missing objects, so it does not catch provider payload drift with a valid sidecar or Drive `appProperties` hash. Add a download inspection check equivalent to upload inspection: compare returned payload length and stripped `metadata.content_hash` against the manifest entry, and cover the mismatch with a real `LocalFileSystemProvider` object whose stored payload differs from the manifest.

Resolution: resolved on re-review. `inspect_remote_mirror_download` now reads both payload and metadata, checks them through `_provider_payload_matches_manifest_entry`, and emits `PARTIAL_DOWNLOAD` on manifest-to-provider drift. Upload inspection now uses the same helper. `test_remote_mirror_download_inspection_detects_ciphertext_drift` covers the drift path with a real `LocalFileSystemProvider` object.

## S43-002 | MEDIUM | Stale mirrors more than one local revision behind are classified as revision conflicts

`_compare_manifest_objects` marks a stale mirror only when `remote_entry.storage_revision_id == local_entry.previous_storage_revision_id`. That detects the immediate predecessor case covered by the current test, but a mirror that last synced at revision A while local storage has advanced through B to C is still stale and is instead reported as `REVISION_CONFLICT` because the local manifest retains only C's immediate previous revision B. This blurs the required stale-mirror versus conflict distinction and can send a recoverable catch-up condition down the conflict path. Use revision timestamps and manifest watermarks, or persist enough lineage metadata, to classify older remote revisions as stale when they are behind the local object timeline rather than divergent. Add a real repository test that saves the same secure object at least three times and compares the first manifest with the latest manifest.

Resolution: resolved after S440. Secure-object rows now preserve `revision_ancestor_ids`; raw rows expose that ancestry without decrypting payloads; remote mirror manifests carry revision ancestry; and `_is_stale_remote_entry` treats a remote revision as stale only when its revision id is the local immediate predecessor or appears in the local ancestry tuple. `test_remote_mirror_comparison_detects_older_stale_remote_revision` covers a real three-save repository sequence where the first manifest is compared against the latest manifest.

## S43-003 | LOW | Mirror inspection helpers are not yet wired into the operator sync path

The new detection helpers are exported from `src/aeat/adapters/outbound/storage/__init__.py`, but repository search found uses only in tests and exports. The current Google sync push path uploads ciphertext objects and persists manifests, but does not call `inspect_remote_mirror_upload`, `inspect_remote_mirror_download`, or `compare_remote_mirror_manifests` before reporting success. If this is intentionally deferred to the next remote-mirror step, keep it tracked there; otherwise the production command can complete without surfacing the partial upload, partial download, stale mirror, or revision conflict conditions that S43 introduces.

## S43-004 | MEDIUM | Timestamp-only stale fallback can mask divergent older remote revisions

`_is_stale_remote_entry` now classifies any remote entry with `revision_written_at` older than the local entry as `STALE_MIRROR`, even when the remote revision id and previous revision id are not in the local entry's lineage. A divergent remote manifest with an unrelated revision id, unrelated previous revision id, and an older timestamp is therefore reported as stale instead of `REVISION_CONFLICT`. A separate probe also showed the timestamp comparison can raise `TypeError` when one manifest timestamp is offset-aware and the other is offset-naive, which means comparison can fail before returning a typed `RemoteMirrorInspection`. Keep S43-002 closed for the multi-revision stale case, but tighten the fallback so timestamps do not override lineage evidence for true conflicts and normalize timestamp awareness before comparison.

Resolution: resolved on final re-review. `_is_stale_remote_entry` now refuses the timestamp fallback when both entries expose incompatible `previous_storage_revision_id` values, preserving `REVISION_CONFLICT` for older divergent revisions with conflicting lineage evidence. `_normalise_revision_timestamp` prevents offset-aware versus offset-naive timestamp comparison crashes. Tests now cover naive stale timestamps and older divergent revisions remaining `REVISION_CONFLICT`.

## S43-005 | MEDIUM | Stale detection remains limited by one-hop revision lineage depth

The S43-004 remediation correctly prevents timestamps from overriding explicit incompatible previous revision ids, but one-hop lineage was not enough to distinguish a true older ancestor from an unrelated older root revision. A remote root revision with `previous_storage_revision_id=None` could only be handled conservatively as conflict, which broke the required stale classification for mirrors more than one revision behind.

Resolution: resolved in S440. `secure_objects` now persists revision ancestry, `SecureObjectRawRow` carries it as structured data, and `RemoteMirrorObjectManifest` includes `revision_ancestor_ids`. Stale classification now uses revision-id ancestry instead of timestamp fallback. The three-save real repository test classifies the first manifest as `STALE_MIRROR`, while `test_remote_mirror_comparison_keeps_unknown_older_root_revision_conflict` proves an unrelated older root revision remains `REVISION_CONFLICT`.

## Review Notes

No S43 residual findings remain open. The scoped tests use real `SecureObjectRepository`, `EphemeralMasterKeyProvider`, SQLite-backed storage, and `LocalFileSystemProvider`; no fakes, mocks, stubs, monkeypatches, skips, or xfails were found in the reviewed S43 mirror test files. Exception handling remains typed for expected provider failures and does not catch broad exceptions. The provider implementations remain bytes-only; the concrete provider boundary continues to treat ciphertext as opaque payload.

Validation run: `uv run --no-sync pytest -q src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/adapters/outbound/storage/test_foundation.py` passed with 16 tests.

Re-review validation run: `uv run --no-sync pytest -q src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/adapters/outbound/storage/test_foundation.py` passed with 18 tests.

Final re-review validation was rerun after S440: `uv run --no-sync pytest -q src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/adapters/outbound/storage/test_foundation.py` passed with 27 tests. `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/sql/test_secure_objects.py` passed with 41 tests. Targeted Ruff over the storage, mirror, and secure-object ancestry surfaces passed.

2026-06-03 continuation validation under `W06.P11.S441`: the enabled Google Drive live provider gate passed with 4 tests; focused storage/Google API tests passed with 46 tests; secure-object persistence/crypto/archive tests passed with 65 tests and 3 pre-existing SQLAlchemy datetime-adapter warnings; the calc-sheets/export and IVA wallet regression batch passed with 49 tests; targeted Ruff over the secure-storage, Google API, secure-object ancestry, and IVA wallet calculation refactor surfaces passed. Manual Drive connector inspection confirmed the app-owned hierarchy, XLSX export succeeded, a bounded formula read succeeded, a bounded value read first hit live HTTP 429 and then succeeded after quota reset.
