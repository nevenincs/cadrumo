---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S152]]'
---

# `secure-storage-production-hardening` `W12.P26.S152` Review

## S152-001 | PASS | Attachments are enrolled in secure-object runtime storage

Attachment blobs save under `ATTACHMENT_BLOB_NAMESPACE`; manifests save under `ATTACHMENT_MANIFEST_NAMESPACE`. Both namespace definitions are FINANCIAL-class registered secure-object namespaces, and the store resolves its repository through the active-bucket runtime route unless a test/integration repository is injected.

## S152-002 | PASS | Logical SQL markers are centralized

The store previously constructed `Path("db://secure_objects") / namespace` locally. That repeated the secure-object hierarchy grammar outside the namespace registry.

Resolution: logical markers now use `secure_object_namespace_logical_path()` so attachment namespace markers derive from the same registry path grammar used by other hardened profile stores without passing dummy object keys.

## S152-003 | PASS | Attachment errors are localized and avoid source-path leakage

Source-read failure previously raised `AttachmentPersistenceError(f"unable to read attachment source: {source}")`, exposing the caller-supplied path. Manifest and blob failures also relied only on raw English messages.

Resolution: the adapter now supplies translated message keys already registered for the attachment error family and structured context. The source-read refusal keeps the diagnostic operation and surface while omitting the full source path. A debug log records only the error type.

## S152-004 | PASS | Tests exercise real attachment behavior

The added tests instantiate the real `AttachmentStore`, inspect logical markers, and exercise an actual missing source path through `put_file()`, `build_error_envelope()`, and `resolve_error_message()`. No fakes, mocks, stubs, monkeypatches, skips, or xfails are used.

## S152-005 | FIXED BEFORE COMMIT | Embedded manifest envelope metadata drift now fails closed

The initial implementation only validated the repository row classification and schema metadata. A reviewer found that a tampered embedded manifest envelope could drift to a different classification or schema version while still returning an `Attachment` payload.

Resolution: `load_manifest()` and `iter_manifests()` now validate the embedded manifest envelope classification and schema version before returning attachment manifests. Real tamper tests mutate stored encrypted rows and assert localized `AttachmentValidationError` context for both drift classes.

## S152-006 | FIXED BEFORE COMMIT | Plan drift corrected for next wave item

The plan had `W12.P26.S153` checked while `AFR-051` was still pending. That overstated execution progress and would hide the blob-store plaintext-exception step from the next wave.

Resolution: `W12.P26.S153` was re-opened through `vaultspec-core vault plan step uncheck`. A follow-up review found the adjacent row cluster still drifting; `W12.P26.S153` and `W12.P26.S154` are now pending and match pending `AFR-051` / `AFR-052`.

## S152-007 | FIXED BEFORE COMMIT | Malformed manifest payloads now localize

The reviewer found that non-UTF-8 manifest bytes and malformed JSON shapes could escape as raw parser exceptions instead of localized `AttachmentValidationError`.

Resolution: manifest read paths now use a shared decode/shape/JSON-mode validation helper. `load_manifest()` and `iter_manifests()` both reject non-UTF-8 bytes, non-object envelopes, and non-object manifest payloads as localized `manifest_payload` validation failures before returning any attachment.

## S152-008 | FIXED BEFORE COMMIT | Manifest iteration no longer uses hashed lookup keys as natural IDs

The reviewer found that `iter_manifests()` passed the secure-object row `object_key` into the manifest decoder. Listed secure-object records expose the hashed lookup digest as bytes, not the original natural attachment ID, causing valid manifests to fail with raw JSON serialization errors.

Resolution: `iter_manifests()` now derives the natural attachment ID from the decrypted manifest payload `sha256` field and validates it as a digest before reconstructing the `Attachment` envelope. The main roundtrip test now asserts that a valid stored manifest is returned by `iter_manifests()`.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_attachment_store_roundtrip.py src/aeat/adapters/persistence/storage/test_namespace_registry.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "attachment or secure_object_namespace_logical_path or secure_object_logical_path"` passed with 14 selected tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/attachment.py src/aeat/adapters/persistence/storage/test_attachment_store_roundtrip.py src/aeat/adapters/persistence/storage/_namespace_registry.py src/aeat/adapters/persistence/storage/test_namespace_registry.py src/aeat/adapters/persistence/storage/__init__.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed.
- Case-sensitive touched-file hygiene scan found no broad exception catches, suppressing pragmas, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, raw UTF-8 literals, local `Path("db://secure_objects")` construction, direct settings construction, or direct environment access.
- Final focused reviewer pass returned no findings after the `iter_manifests()` natural-ID derivation fix.

Disposition: close `AFR-050` as `runtime-default`.
