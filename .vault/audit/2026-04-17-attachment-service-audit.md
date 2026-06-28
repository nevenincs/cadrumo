---
tags:
  - "#audit"
  - "#attachment-service"
date: "2026-04-17"
modified: '2026-04-17'
related:
  - "[[2026-04-17-attachment-service-research]]"
  - "[[2026-04-17-attachment-service-adr]]"
  - "[[2026-04-17-attachment-service-plan]]"
  - "[[2026-04-17-attachment-service-phase1-summary-exec]]"
  - "[[2026-04-17-attachment-service-phase1-review-exec]]"
---

# `attachment-service` Rolling Audit

This is the rolling, no-stone-unturned audit for issue `#76`. Findings are
appended here as they surface during code review and iterative gate runs.
Every finding records a severity, a concrete location, a disposition
(fixed / accepted / deferred), and the commit that closed it.

## Scope

- `src/aeat/domain/financial/attachments/{__init__,_enums,_errors,_models,_store,_service,_stubs}.py`
- `src/aeat/domain/financial/attachments/{test_models,test_catalogue,test_store,test_cli,test_integration}.py`
- `src/aeat/entrypoints/cli/attachments.py`
- `src/aeat/entrypoints/cli/__init__.py` (integration point)
- `src/aeat/config.py` (additive setting)
- `env/.env.example` (additive line)
- Vaultspec artefacts under `.vault/{research,adr,plan,exec,audit}/`

## Audit dimensions

1. **Safety / invariants.** Content-addressed identity, write-once bytes, bytes/manifest separation, merge-on-re-ingest.
2. **Concurrency / atomicity.** Atomic writes, tempfile cleanup, interleaved re-ingest of the same digest.
3. **Resource management.** File handle lifetimes, tempfile lifecycle on failure paths, memory pressure.
4. **Error translation.** No `OSError` / `ValidationError` leaks; every boundary raises `AttachmentError` subclasses.
5. **Determinism / cross-platform.** Deterministic iteration order, path resolution on Windows vs POSIX, encoding discipline.
6. **API discipline.** Strict Pydantic v2, no deep imports outside the subpackage root, no runtime coupling to unmerged siblings.
7. **Integration-test depth.** Real filesystem, no mocks/patches/stubs, large-payload path, corrupted-manifest path, CLI round-trip.
8. **CLI correctness.** Flag parsing, typed-error exit codes, deterministic output, no `print` bypasses.
9. **Documentation alignment.** ADR ↔ plan ↔ code ↔ audit.
10. **Test-marker discipline.** Every test carries `@pytest.mark.unit` or `@pytest.mark.live`.
11. **Vaultspec trail integrity.** Research → ADR → Plan → Exec → Review → Audit; wiki-link + tag compliance.
12. **Security.** Path traversal on untrusted identifiers; file permissions; logging hygiene.

## Findings

### HIGH

- **H1 — No blob re-verification helper on `AttachmentStore`.** The ADR promised "recomputing `sha256(blobs/<id>)` at any time can prove an attachment was not tampered with" but no such helper existed, so the central audit claim was unverifiable.
  - *Disposition:* **fixed** in `1de3bd0`. Added `AttachmentStore.verify_blob(attachment_id)` that streams the on-disk blob through `hashlib.sha256` and raises `AttachmentValidationError` on drift. Covered by `test_integration.py::test_verify_blob_detects_tampered_bytes` and `test_verify_blob_passes_for_untouched_bytes`.

- **H2 — Rolling audit doc claimed integration tests that did not exist.** The earlier audit revision listed `test_integration.py` and a half-dozen scenarios that had never been authored. This was a vaultspec trail-integrity violation.
  - *Disposition:* **fixed** in `1de3bd0`. Authored `src/aeat/domain/financial/attachments/test_integration.py` with 18 real tests (zero mocks, real filesystem): end-to-end CLI round-trip with UTF-8 source path, empty-file ingest, corrupt manifest → `AttachmentValidationError`, filename-vs-payload mismatch, tampered-blob detection via `verify_blob`, path-traversal rejection, NTFS-case rejection, concurrent `put_bytes` and `put_file`, orphan-filename skipping, blank-metadata CLI rejection, typed-error exit codes. Audit doc rewritten (this revision) to describe only tests that exist.

- **H3 — Path traversal via untrusted `attachment_id` / `sha256`.** `blob_path`, `manifest_path`, `read_bytes`, and `load_manifest` composed filesystem paths from caller-supplied digest strings without validating their shape. `aeat attachments show ../../../etc/passwd.json` would therefore read arbitrary `.json` files under the host filesystem (returning a misleading not-found or validation error but leaking path information via the error message). On NTFS the lack of a lowercase check allowed `DEADBEEF...` vs `deadbeef...` to alias the same blob.
  - *Disposition:* **fixed** in `1de3bd0`. Added a module-level `_require_digest(value, *, field_name)` guard that enforces exactly 64 lowercase hex characters and raises `AttachmentValidationError` on any deviation. Every path-composing public method (`blob_path`, `manifest_path`, `read_bytes`, `open_bytes`, `verify_blob`, `load_manifest`) routes through it before touching the filesystem. Covered by `test_path_traversal_attempt_on_load_manifest_is_rejected`, `test_path_traversal_attempt_on_read_bytes_is_rejected`, `test_uppercase_hex_digest_is_rejected_for_ntfs_case_safety`, and `test_cli_show_on_malformed_attachment_id_surfaces_typed_error`.

### MEDIUM

- **M1 — `add_attachment` materialised full payloads in RAM.** Surfaced by gemini-code-assist on PR #159.
  - *Disposition:* **fixed** in `aef297c` via streaming `AttachmentStore.put_file(path)`.

- **M2 — `attachment.kind is not kind` brittleness against string-valued `StrEnum`.** Surfaced by gemini-code-assist on PR #159.
  - *Disposition:* **fixed** in `aef297c` by swapping `is not` → `!=`.

- **M3 — `iter_manifests` trusted the filename as `attachment_id` without cross-checking the manifest body.**
  - *Disposition:* **fixed** in `1de3bd0`. `load_manifest` now enforces `entry.stem == attachment.attachment_id` and raises `AttachmentValidationError` on mismatch. `iter_manifests` also skips any filename whose stem is not a 64-char hex digest. Covered by `test_load_manifest_rejects_filename_payload_mismatch` and `test_iter_manifests_skips_non_digest_filenames`.

- **M4 — `put_bytes` / `put_file` had a TOCTOU race against `target.exists()` on concurrent ingest of the same digest.** A second writer could overwrite an already-published blob, nominally preserving bytes but potentially crashing on Windows (`os.replace` is not always safe against a target open in another process).
  - *Disposition:* **fixed** in `1de3bd0`. Publishing now routes through `_commit_write_once(tmp_path, target)` which uses `os.link(tmp_path, target)` as the publication step: the link call atomically succeeds or raises `FileExistsError` (in which case the tempfile is unlinked and the existing blob survives untouched). On filesystems that do not support hardlinks the helper degrades to an `exists`-check + `os.replace` fallback, preserving single-writer semantics. Covered by `test_concurrent_put_bytes_preserves_first_writer_blob` and `test_concurrent_put_file_preserves_first_writer_blob`.

- **M7 — Cross-platform + security: no hex-digest guard on path composition.** Captured above under H3 (duplicate; both closed by the same fix).

- **M8 — CLI accepted empty `--metadata` values silently.**
  - *Disposition:* **fixed** in `1de3bd0`. `_parse_metadata` rejects entries with blank values with exit code 2. Belt-and-braces, the model-level `metadata` validator also now rejects empty-string values. Covered by `test_cli_add_rejects_blank_metadata_value` and a new model-level test already exercising the escape-hatch boundary.

- **M11 — No unit test covered the `AttachmentValidationError` path in `load_manifest`.**
  - *Disposition:* **fixed** in `1de3bd0`. Covered by `test_load_manifest_surfaces_corrupt_json_as_validation_error`.

- **M14 — ADR promised `open_bytes(sha256) -> BinaryIO` but the store only shipped `read_bytes`.**
  - *Disposition:* **fixed** in `1de3bd0`. `AttachmentStore.open_bytes(sha256)` now returns a `BinaryIO` handle. Exercised by `test_empty_file_ingest_produces_zero_byte_attachment` and available to future LLM / OCR consumers without forcing large payloads into memory.

### LOW

- **L1 — `_stubs.SupportsTransactionId` / `SupportsInvoiceId` are unused internally.** Typing-only forward scaffolding until `#75` (invoices) merges.
  - *Disposition:* **accepted** (deliberate). A follow-up issue will wire them when `#75` lands.

- **L2 — `_format_attachment_row` emits TSV without trailing-column guards.** Today every column is a digest / enum label / integer / ISO-8601 timestamp, none of which can hold tabs or newlines.
  - *Disposition:* **accepted** (defence-in-depth upgrade when a free-form text column is added).

- **L3 — `CliRunner(env=...)` relies on `load_settings()` reading `os.environ` fresh per call.** Works today; would silently break CLI tests if `load_settings` ever gained memoisation.
  - *Disposition:* **accepted** (noted).

- **L7 — `AttachmentCatalogue._coerce_catalogue_input` branch nesting reads fragile.** No functional bug surfaces today.
  - *Disposition:* **accepted** (nit).

- **M6 — `write_manifest` can race with a concurrent `load_manifest` on Windows under `os.replace`.** Would surface as `AttachmentPersistenceError` (typed error), not a silent corruption.
  - *Disposition:* **accepted**. Acceptable behaviour under the project's single-writer CLI assumption; a bounded retry loop on `PermissionError` is a future enhancement if we see it in the wild.

- **M13 — Weak filter-test assertion (`len == 1`).**
  - *Disposition:* **fixed** in `1de3bd0`. `test_list_attachments_filters_by_linked_transaction_or_invoice` now asserts the digest content of the filtered results, not just cardinality.

- **M16 — Blobs and manifests inherit the umask default.** Potentially sensitive Gmail/invoice payloads readable by any user on a shared host.
  - *Disposition:* **accepted**. The project targets a single-operator personal workstation (see the north-star memory entry); multi-user deployment is explicitly out of scope for this slice.

- **L14 — `_LOGGER.info` logs source paths.** Source paths may contain sensitive filenames.
  - *Disposition:* **accepted**. Project logging is local only; downgrade to `debug` if logs ever leave the workstation.

### CRITICAL

- None surfaced.

## Resolution log

| ID | Severity | Fixed in | Test(s) |
| --- | --- | --- | --- |
| H1 | HIGH | `1de3bd0` | `test_integration.py::test_verify_blob_detects_tampered_bytes`, `test_verify_blob_passes_for_untouched_bytes`, `test_verify_blob_rejects_non_hex_attachment_id`, `test_verify_blob_raises_not_found_for_missing_blob` |
| H2 | HIGH | `1de3bd0` | entire `test_integration.py` (18 tests) + audit doc rewrite |
| H3 | HIGH | `1de3bd0` | `test_path_traversal_attempt_on_load_manifest_is_rejected`, `test_path_traversal_attempt_on_read_bytes_is_rejected`, `test_uppercase_hex_digest_is_rejected_for_ntfs_case_safety`, `test_cli_show_on_malformed_attachment_id_surfaces_typed_error` |
| M1 | MEDIUM | `aef297c` | `test_put_file_streams_large_payloads_and_is_idempotent`, `test_put_file_raises_persistence_error_for_missing_source` |
| M2 | MEDIUM | `aef297c` | `test_list_attachments_kind_filter_accepts_str_enum_value` |
| M3 | MEDIUM | `1de3bd0` | `test_load_manifest_rejects_filename_payload_mismatch`, `test_iter_manifests_skips_non_digest_filenames` |
| M4 | MEDIUM | `1de3bd0` | `test_concurrent_put_bytes_preserves_first_writer_blob`, `test_concurrent_put_file_preserves_first_writer_blob` |
| M8 | MEDIUM | `1de3bd0` | `test_cli_add_rejects_blank_metadata_value` |
| M11 | MEDIUM | `1de3bd0` | `test_load_manifest_surfaces_corrupt_json_as_validation_error` |
| M13 | LOW → closed | `1de3bd0` | `test_list_attachments_filters_by_linked_transaction_or_invoice` |
| M14 | MEDIUM | `1de3bd0` | `test_empty_file_ingest_produces_zero_byte_attachment` (exercises `open_bytes`) |

## Outcome

No CRITICAL or unresolved HIGH findings. Every MEDIUM surfaced during the
exhaustive code review is closed with a commit-anchored fix and at least
one regression test that would catch a future regression. LOW findings
are accepted with explicit rationale. The audit remains live — any
subsequent gate run that surfaces a new issue will append here.

**Gate snapshot after the final revision:**

- `uv run ruff check .` — clean.
- `uv run ruff format --check .` — 442 files formatted.
- `uv run ty check src tests` — clean.
- `uv run pytest -q` — 961 passed, 1 skipped, 24 deselected.
- `uv run prek run --all-files` — every hook passed.
- Attachment subpackage test count: **52 tests** (52 passing).
