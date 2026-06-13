---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S152'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s152-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S152`

Closed `AFR-050` for the encrypted attachment store.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/attachment.py` against the `secure-object` and `plain-file` scanner signals.
- Confirmed attachment blobs and manifests persist through `SecureObjectRepository` under the registered FINANCIAL attachment namespaces.
- Replaced local `Path("db://secure_objects")` marker construction with the centralized `secure_object_namespace_logical_path()` namespace helper.
- Replaced raw UTF-8 encode/decode literals in attachment manifest persistence and tests with `UTF_8_ENCODING`.
- Added localized attachment storage errors for digest validation, source-read persistence failure, not-found cases, manifest validation, and digest drift.
- Removed full source path echoing from the source-read persistence refusal and added sanitized debug evidence with error type only.
- Added fail-closed manifest-envelope validation for embedded classification and schema-version drift before attachment manifests are returned.
- Added manifest payload shape/decode validation so malformed stored bytes and JSON structures surface as localized attachment validation errors.
- Fixed manifest iteration to derive natural attachment IDs from decrypted manifest payloads instead of hashed secure-object lookup keys.
- Added real attachment tests for namespace-derived logical paths, localized source-read error envelope privacy, tampered manifest envelope metadata, malformed manifest read paths, and valid manifest iteration.
- Closed `W12.P26.S152` through `vaultspec-core vault plan step check` and aligned the AFR register row to `closed`.
- Re-opened `W12.P26.S153` through `vaultspec-core vault plan step uncheck` because `AFR-051` remains pending until the blob-store plaintext-exception step is executed.
- Repaired `W12.P26.S153` and `W12.P26.S154` checkbox drift after repeated CLI uncheck calls reintroduced checked states in the adjacent pending rows.
- Completed a final reviewer pass with no findings after the manifest iteration fix.

## Outcome

`AFR-050` is closed as `runtime-default`.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_attachment_store_roundtrip.py src/aeat/adapters/persistence/storage/test_namespace_registry.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "attachment or secure_object_namespace_logical_path or secure_object_logical_path"`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/attachment.py src/aeat/adapters/persistence/storage/test_attachment_store_roundtrip.py src/aeat/adapters/persistence/storage/_namespace_registry.py src/aeat/adapters/persistence/storage/test_namespace_registry.py src/aeat/adapters/persistence/storage/__init__.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` reported only `PLAN022`.
- Case-sensitive touched-file hygiene scan found no broad exception catches, suppressing pragmas, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, raw UTF-8 literals, local `Path("db://secure_objects")` construction, direct settings construction, or direct environment access.

## Notes

Attachment storage remains runtime-default secure-object storage. The remaining plain-file behavior is the explicit caller-supplied source read in `put_file()` before bytes enter the encrypted object backend.
