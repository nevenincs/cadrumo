---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
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

Resolution: resolved for the reported stale-mirror gap on re-review. `_compare_manifest_objects` now delegates stale detection to `_is_stale_remote_entry`, which preserves the immediate-predecessor check and also treats an older remote `revision_written_at` as stale. `test_remote_mirror_comparison_detects_older_stale_remote_revision` covers a real three-save repository sequence where the first manifest is compared against the latest manifest.

## S43-003 | LOW | Mirror inspection helpers are not yet wired into the operator sync path

The new detection helpers are exported from `src/aeat/adapters/outbound/storage/__init__.py`, but repository search found uses only in tests and exports. The current Google sync push path uploads ciphertext objects and persists manifests, but does not call `inspect_remote_mirror_upload`, `inspect_remote_mirror_download`, or `compare_remote_mirror_manifests` before reporting success. If this is intentionally deferred to the next remote-mirror step, keep it tracked there; otherwise the production command can complete without surfacing the partial upload, partial download, stale mirror, or revision conflict conditions that S43 introduces.

## S43-004 | MEDIUM | Timestamp-only stale fallback can mask divergent older remote revisions

`_is_stale_remote_entry` now classifies any remote entry with `revision_written_at` older than the local entry as `STALE_MIRROR`, even when the remote revision id and previous revision id are not in the local entry's lineage. A divergent remote manifest with an unrelated revision id, unrelated previous revision id, and an older timestamp is therefore reported as stale instead of `REVISION_CONFLICT`. A separate probe also showed the timestamp comparison can raise `TypeError` when one manifest timestamp is offset-aware and the other is offset-naive, which means comparison can fail before returning a typed `RemoteMirrorInspection`. Keep S43-002 closed for the multi-revision stale case, but tighten the fallback so timestamps do not override lineage evidence for true conflicts and normalize timestamp awareness before comparison.

Resolution: resolved on final re-review. `_is_stale_remote_entry` now refuses the timestamp fallback when both entries expose incompatible `previous_storage_revision_id` values, preserving `REVISION_CONFLICT` for older divergent revisions with conflicting lineage evidence. `_normalise_revision_timestamp` prevents offset-aware versus offset-naive timestamp comparison crashes. Tests now cover naive stale timestamps and older divergent revisions remaining `REVISION_CONFLICT`.

## S43-005 | LOW | Stale detection remains limited by one-hop revision lineage depth

The S43-004 remediation correctly prevents timestamps from overriding explicit incompatible previous revision ids. A residual ambiguity remains when an older remote entry does not expose incompatible lineage evidence, especially a root remote revision with `previous_storage_revision_id=None`: with only one previous revision id in each manifest entry, the comparator cannot prove whether that older revision is an ancestor or an unrelated root revision. The current timestamp fallback intentionally classifies that state as `STALE_MIRROR` to preserve recoverable stale detection for mirrors more than one revision behind. Track this as a lineage-depth limitation for future manifest evolution rather than an active S43-004 blocker.

## Residual Review Notes

The scoped tests use real `SecureObjectRepository`, `EphemeralMasterKeyProvider`, SQLite-backed storage, and `LocalFileSystemProvider`; no fakes, mocks, stubs, monkeypatches, skips, or xfails were found in the reviewed test files. Exception handling remains typed for expected provider failures and does not catch broad exceptions. The provider implementations remain bytes-only; the concrete provider boundary continues to treat ciphertext as opaque payload.

Validation run: `uv run --no-sync pytest -q src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/adapters/outbound/storage/test_foundation.py` passed with 16 tests.

Re-review validation run: `uv run --no-sync pytest -q src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/adapters/outbound/storage/test_foundation.py` passed with 18 tests.

Final re-review validation was not rerun by reviewer; implementer reported `ruff` passed and focused pytest reported 20 passed.
