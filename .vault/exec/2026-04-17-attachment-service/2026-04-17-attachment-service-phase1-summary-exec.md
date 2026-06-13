---
tags:
  - "#exec"
  - "#attachment-service"
date: "2026-04-17"
modified: '2026-04-17'
related:
  - "[[2026-04-17-attachment-service-plan]]"
  - "[[2026-04-17-attachment-service-adr]]"
  - "[[2026-04-17-attachment-service-research]]"
---

# `attachment-service` `phase-1` summary

## Outcome

Delivered issue `#76` end-to-end in one execution pass per the plan's sequential structure. All local gates are green:

- `uv run ruff check .` → clean.
- `uv run ruff format --check .` → 438 files already formatted.
- `uv run ty check src tests` → all checks passed.
- `uv run pytest -q` → 933 passed, 1 skipped, 24 deselected.
- `uv run prek run --all-files` → every hook passed.

## Artefacts

- New subpackage `src/aeat/domain/financial/attachments/` with:
  - `_enums.py` — `AttachmentKind`, `AttachmentSource` (`StrEnum`).
  - `_errors.py` — `AttachmentError` hierarchy inheriting from `AeatError`.
  - `_models.py` — strict frozen pydantic v2 `Attachment` (with `attachment_id == sha256` invariant, ordered dedup'd link tuples, `str`-only metadata escape hatch) and `AttachmentCatalogue`.
  - `_store.py` — `AttachmentStore` (frozen pydantic model) with write-once `put_bytes`, atomic manifest writes, and sorted `iter_manifests`.
  - `_service.py` — `add_attachment` merge-on-re-ingest semantics, `load_attachment`, `list_attachments`.
  - `_stubs.py` — typing-only `SupportsTransactionId` / `SupportsInvoiceId` Protocols.
  - `test_models.py`, `test_catalogue.py`, `test_store.py`, `test_cli.py` — 31 unit tests covering hash invariants, dedup, write-once, link merge, orphan-blob handling, metadata parsing, CLI surfaces.
- New CLI module `src/aeat/entrypoints/cli/attachments.py` wired into the root `aeat` app at `aeat attachments`.
- Settings: additive `AEAT_ATTACHMENTS_DIR` in `src/aeat/config.py` + `env/.env.example`.
- Vaultspec trail: research, ADR, plan, and this summary.

## Verification against plan

- `Attachment` round-trips via `model_validate_json` (covered by `test_models.py::test_attachment_round_trips_through_json`).
- `attachment_id == sha256` rejection path covered.
- Naive `captured_at`, invalid hex, empty metadata keys, non-string metadata values all rejected.
- Linked-ID tuples dedupe with first-seen ordering.
- `AttachmentStore.put_bytes` write-once invariant asserted against the `mtime_ns` of the original blob.
- Re-ingest merges `linked_transaction_ids` and `linked_invoice_ids` with no duplicate blob and a single manifest file.
- `list_attachments` filters by `linked_to` across both link sets and by `kind`.
- Orphan blob without a manifest does not surface via `list_attachments` or `iter_manifests`.
- CLI smoke tests exercise `aeat attachments add/list/show`, `--metadata` parsing rules, and missing-manifest exit path.

## Deviations from the plan

- None. All six plan-audit clarifications (store frozen config, deterministic iteration order, error translation for source-read failures, `--metadata` parsing contract, orphan-blob assertion, `bytes_size == len(data)` invariant) were folded into the implementation and tests before execution.

## Next steps

Handoff to code-review, PR creation, and automated-review triage per the handover prompt's remaining steps.
