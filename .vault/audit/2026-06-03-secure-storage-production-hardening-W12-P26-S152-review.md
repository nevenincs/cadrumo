---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S152]]'
---

# `secure-storage-production-hardening` `W12.P26.S152` Review

## S152-001 | PASS | Attachments are enrolled in secure-object runtime storage

Attachment blobs save under `ATTACHMENT_BLOB_NAMESPACE`; manifests save under `ATTACHMENT_MANIFEST_NAMESPACE`. Both namespace definitions are FINANCIAL-class registered secure-object namespaces, and the store resolves its repository through the active-bucket runtime route unless a test/integration repository is injected.

## S152-002 | PASS | Logical SQL markers are centralized

The store previously constructed `Path("db://secure_objects") / namespace` locally. That repeated the secure-object hierarchy grammar outside the namespace registry.

Resolution: logical markers now use `secure_object_logical_path()` so attachment markers derive from the same registry path grammar used by other hardened profile stores.

## S152-003 | PASS | Attachment errors are localized and avoid source-path leakage

Source-read failure previously raised `AttachmentPersistenceError(f"unable to read attachment source: {source}")`, exposing the caller-supplied path. Manifest and blob failures also relied only on raw English messages.

Resolution: the adapter now supplies translated message keys already registered for the attachment error family and structured context. The source-read refusal keeps the diagnostic operation and surface while omitting the full source path. A debug log records only the error type.

## S152-004 | PASS | Tests exercise real attachment behavior

The added tests instantiate the real `AttachmentStore`, inspect logical markers, and exercise an actual missing source path through `put_file()`, `build_error_envelope()`, and `resolve_error_message()`. No fakes, mocks, stubs, monkeypatches, skips, or xfails are used.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_attachment_store_roundtrip.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "attachment"` passed with 7 selected tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/attachment.py src/aeat/adapters/persistence/storage/test_attachment_store_roundtrip.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed.
- Case-sensitive touched-file hygiene scan found no broad exception catches, suppressing pragmas, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, raw UTF-8 literals, local `Path("db://secure_objects")` construction, direct settings construction, or direct environment access.

Disposition: close `AFR-050` as `runtime-default`.
