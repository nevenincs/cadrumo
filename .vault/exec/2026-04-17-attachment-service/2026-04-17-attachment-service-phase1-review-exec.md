---
tags:
  - "#exec"
  - "#attachment-service"
date: "2026-04-17"
modified: '2026-04-17'
related:
  - "[[2026-04-17-attachment-service-plan]]"
  - "[[2026-04-17-attachment-service-adr]]"
  - "[[2026-04-17-attachment-service-phase1-summary-exec]]"
---

# `attachment-service` `phase-1` review

## Verdict

Approved — no CRITICAL or HIGH issues. Safe to open PR after rebasing onto current `main`.

## Coverage against the 8 review priorities

1. **Safety / invariants.** `put_bytes` is content-addressed with `hashlib.sha256` + atomic `os.replace` rename and skips re-writes when a blob already exists — write-once honoured. `Attachment._enforce_attachment_id_matches_sha256` enforces the `attachment_id == sha256` equality in the model. Bytes live under `blobs/`, manifests under `manifests/`. No code path can violate these invariants.
2. **Link merge correctness.** `_service.add_attachment` loads any existing manifest first, concatenates `existing + new` for both link tuples, and the model's validators dedupe preserving first-seen order. Merge remains non-destructive when the caller supplies no new links.
3. **Error translation.** `OSError → AttachmentPersistenceError` at every filesystem boundary (source read, blob read/write, manifest read/write, manifest listing). `ValidationError → AttachmentValidationError` in `load_manifest` and `add_attachment`. `AttachmentNotFoundError` is used consistently for missing lookups.
4. **Strict Pydantic v2 discipline.** `ConfigDict(strict=True, frozen=True, extra="forbid")` applied to `Attachment`, `AttachmentCatalogue`, and `AttachmentStore`. The `metadata` escape hatch is narrow: string keys only (non-blank), string values only, frozen via `MappingProxyType` at runtime, serialized back to plain `dict`.
5. **Subpackage discipline.** No external deep imports into `aeat.domain.financial.attachments._*`. `_stubs.py` declares typing-only Protocols with no runtime imports. External callers go through `aeat.domain.financial.attachments.__init__`.
6. **Tests.** No mocks, patches, stubs, skips, or tautologies. Assertions are concrete (byte-level reads, `st_mtime_ns` for idempotency, sorted-filename iteration, orphan-blob suppression, CLI re-ingest merge, metadata parse rules).
7. **CLI correctness.** `add` / `list` / `show` behave correctly. `--metadata key=value` enforces the `=` separator, non-blank key, and duplicate-key rejection with exit code 2. `AttachmentError` subclasses are caught and surfaced cleanly with exit code 2.
8. **Settings alignment.** Only one new field (`aeat_attachments_dir`) and one new line in `env/.env.example`. `tests/test_config.py` stays green.

## MEDIUM / LOW observations

- LOW — `_stubs.py` Protocols are pure forward-looking scaffolding until `#75` (invoices) lands. No action needed; a future ADR extension for invoice wiring will exercise them.
- LOW — `_format_attachment_row` emits TSV without a trailing-column guard. All current fields are ASCII digest / enum / int / ISO-8601 so embedded tabs or newlines are not possible today.
- LOW — Branch `feature/76-attachment-service` is behind `main` at review time. Rebase before PR opens.
- LOW — `CliRunner(env=...)` relies on `load_settings()` reading `os.environ` fresh per call. Safe today; worth a comment if caching is introduced later.

## Outcome

Pipeline may proceed to PR.
