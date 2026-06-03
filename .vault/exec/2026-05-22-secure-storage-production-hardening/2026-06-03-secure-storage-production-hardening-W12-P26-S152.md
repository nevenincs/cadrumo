---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
step_id: 'S152'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S152-review]]'
---

# `secure-storage-production-hardening` `W12.P26.S152`

Closed `AFR-050` for the encrypted attachment store.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/attachment.py` against the `secure-object` and `plain-file` scanner signals.
- Confirmed attachment blobs and manifests persist through `SecureObjectRepository` under the registered FINANCIAL attachment namespaces.
- Replaced local `Path("db://secure_objects")` marker construction with the centralized `secure_object_logical_path()` namespace helper.
- Replaced raw UTF-8 encode/decode literals in attachment manifest persistence and tests with `UTF_8_ENCODING`.
- Added localized attachment storage errors for digest validation, source-read persistence failure, not-found cases, manifest validation, and digest drift.
- Removed full source path echoing from the source-read persistence refusal and added sanitized debug evidence with error type only.
- Added real attachment tests for namespace-derived logical paths and localized source-read error envelope privacy.
- Closed `W12.P26.S152` through `vaultspec-core vault plan step check` and aligned the AFR register row to `closed`.

## Outcome

`AFR-050` is closed as `runtime-default`.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_attachment_store_roundtrip.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "attachment"`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/attachment.py src/aeat/adapters/persistence/storage/test_attachment_store_roundtrip.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- Case-sensitive touched-file hygiene scan found no broad exception catches, suppressing pragmas, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, raw UTF-8 literals, local `Path("db://secure_objects")` construction, direct settings construction, or direct environment access.

## Notes

Attachment storage remains runtime-default secure-object storage. The remaining plain-file behavior is the explicit caller-supplied source read in `put_file()` before bytes enter the encrypted object backend.
