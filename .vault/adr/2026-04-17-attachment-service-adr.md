---
tags:
  - "#adr"
  - "#attachment-service"
date: "2026-04-17"
modified: '2026-04-17'
related:
  - "[[2026-04-17-attachment-service-research]]"
  - "[[2026-04-14-transaction-catalogue-adr]]"
  - "[[2026-04-14-transaction-catalogue-plan]]"
---

# `attachment-service` adr: `content-addressed-document-evidence-layer` | (**status:** `accepted`)

## Problem Statement

Issue `#76` must introduce a typed, content-addressed **Attachment** service that links supporting documents — invoice PDFs, Gmail messages, Drive documents, receipts, contracts, arbitrary metadata blobs — to `Transaction` (`#74`, on `main`) and `Invoice` (`#75`, not yet on `main`) records. Every casilla value the system eventually justifies must be traceable through a provenance chain that terminates at one or more attachments, and the service must keep byte storage separate from metadata storage so byte files are write-once while manifests can evolve as links are recorded.

## Considerations

- `aeat.domain.financial.transactions` is the already-merged downstream consumer of attachment links. Attachments must hold `transaction_id` references as opaque strings and avoid coupling to the transaction runtime type beyond a typing-level Protocol.
- `aeat.domain.financial.invoices/` is still in flight on `#75`, so the attachment package cannot hard-import invoice types. Invoice foreign keys must be plain `str` at runtime with a typing-only `Protocol` placeholder for documentation and IDE help.
- The issue mandates content-addressed storage keyed by the SHA-256 of the stored bytes. Two separate stores are required: raw bytes under `var/financial/attachments/blobs/<sha256>` (extensionless, write-once) and JSON manifests under `var/financial/attachments/manifests/<sha256>.json` (mutable as new links are recorded).
- Deduplication is a natural consequence of content addressing: re-ingesting the same file produces the same `attachment_id`. The ingest path must therefore merge new links into the existing manifest rather than overwrite it.
- The issue carves out `metadata: dict[str, str]` as an explicit escape hatch from the project's Pydantic mandate. It exists for heterogeneous provider-specific metadata (Gmail headers, Drive revision IDs, EXIF dumps) and must be justified here, constrained to `str` values, and kept narrow.
- The CLI surface in the issue body is `aeat attachments ...` at the root of the CLI, parallel to `aeat financial` and `aeat inbox`, not nested under `aeat financial`.

## Constraints

- The public API must be importable only from `aeat.domain.financial.attachments`; callers must not reach into underscored submodules.
- Every persisted and boundary-crossing structure must be strict pydantic v2; closed sets must use `enum.StrEnum`.
- All domain errors must inherit from `aeat.core.errors.AeatError`; logging must use `aeat.core.logging.get_logger(__name__)`.
- Byte files are **write-once**: once a `<sha256>` blob exists under `blobs/`, the service must not overwrite it. A re-ingest of the same bytes becomes a manifest update only.
- `attachment_id` must equal the SHA-256 digest of the stored bytes; the model must reject any payload where the two disagree.
- `sha256` values must be 64-character lowercase hex digests (same discipline as `RawProvenance.source_sha256`).
- `captured_at` must be timezone-aware (same discipline as `RawProvenance.ingested_at`).
- Linked ID tuples must be ordered, immutable, and deduplicated on validation.
- `metadata` values must be strings only; empty keys and non-string values are rejected.
- `var/financial/attachments/` must be a valid default for `AEAT_ATTACHMENTS_DIR`, and the config test in `tests/test_config.py` must stay green by adding the matching field in `env/.env.example`.

## Implementation

- Create `src/aeat/domain/financial/attachments/` with a public `__init__.py` and private underscored modules for enums (`_enums.py`), errors (`_errors.py`), models (`_models.py`), the byte/manifest store (`_store.py`), service helpers (`_service.py`), and typing stubs (`_stubs.py`).
- Define `AttachmentKind` and `AttachmentSource` as `StrEnum` values using the uppercase identifiers listed in the issue.
- Define `Attachment` as a strict frozen pydantic v2 model with:
  - `attachment_id: str` (64-char lowercase hex, equal to `sha256`).
  - `kind: AttachmentKind`, `source: AttachmentSource`.
  - `source_reference: str` (path / Gmail msg-id / Drive file-id / URL), trimmed, non-empty.
  - `sha256: str` (64-char lowercase hex).
  - `mime_type: str` (non-empty), `bytes_size: int` (`ge=0`).
  - `captured_at: datetime` (timezone-aware).
  - `linked_transaction_ids: tuple[str, ...]`, `linked_invoice_ids: tuple[str, ...]` (validated: non-empty strings, deduplicated, deterministic ordering).
  - `metadata: Mapping[str, str]` frozen via `MappingProxyType`, keys trimmed non-empty, values coerced to `str` only.
  - `notes: str` (trimmed; empty allowed).
- Define `AttachmentCatalogue` as a strict pydantic model wrapping `dict[str, Attachment]`, with `__iter__`, `__len__`, `__contains__`, a `get` helper, and a `from_attachments` class constructor that rejects duplicate `attachment_id` values explicitly when building from an iterable. The catalogue keys must match each entry's `attachment_id`.
- Implement `AttachmentStore` as a strict dataclass (or pydantic `BaseModel` holding the root `Path`) that:
  - Exposes `root`, `blobs_dir` (`<root>/blobs`), and `manifests_dir` (`<root>/manifests`).
  - Offers `put_bytes(bytes_payload) -> str` that writes `<blobs>/<sha256>` atomically and returns the hex digest; if the blob already exists, it is left untouched (write-once).
  - Offers `read_bytes(sha256) -> bytes` and `open_bytes(sha256) -> BinaryIO` read paths that raise typed `AttachmentNotFoundError` when missing.
  - Offers `write_manifest(attachment) -> None` and `load_manifest(attachment_id) -> Attachment` for the manifest side, with atomic temp-file replacement matching the transactions subpackage pattern.
  - Offers `iter_manifests() -> Iterator[Attachment]` for enumeration used by the CLI `list` command.
- Implement service-level helpers in `_service.py`:
  - `add_attachment(store, *, path, kind, source, source_reference, mime_type, captured_at, link_transaction_ids, link_invoice_ids, metadata, notes) -> Attachment` — hashes bytes once, writes the blob (idempotent), merges any existing manifest's links with the new links, writes the merged manifest, returns the saved attachment.
  - `load_attachment(store, attachment_id) -> Attachment` — thin typed wrapper.
  - `list_attachments(store, *, linked_to: str | None = None) -> tuple[Attachment, ...]` — filters by linked transaction/invoice identifier when provided.
- Add an `AEAT_ATTACHMENTS_DIR` setting to `aeat.core.config.Settings` defaulting to `PROJECT_ROOT / "var" / "financial" / "attachments"`, and mirror the entry in `env/.env.example`.
- Mount the CLI at the root as `aeat attachments`: a Typer sub-app in `src/aeat/entrypoints/cli/attachments.py` exposing `add`, `list`, and `show` that resolve the store directory from the configured setting.
- Keep invoice/transaction interoperability at typing level via `_stubs.py` Protocols (`SupportsTransactionId`, `SupportsInvoiceId`); runtime foreign-key fields stay `str`.
- Colocated unit tests under `src/aeat/domain/financial/attachments/`:
  - `test_models.py` — validator coverage for hash mismatch, invalid sha256, naive timestamps, empty linked IDs, duplicate linked IDs, invalid metadata shapes.
  - `test_catalogue.py` — catalogue construction, duplicate detection, round-trip via `model_dump_json`.
  - `test_store.py` — dedup semantics, write-once blob invariant, manifest round-trip, link merging on re-ingest, bytes/manifests separation.
  - `test_cli.py` — `aeat attachments add/list/show` smoke via Typer's `CliRunner`, exercising `--link-tx`, `--link-invoice`, and `--linked-to` filters.

## Rationale

- Making `attachment_id == sha256(bytes)` collapses identity and content addressing into a single invariant that is trivially verifiable by re-hashing any blob. Cross-store validation becomes a one-line equality check in the model.
- Separating `blobs/` and `manifests/` under the configured root gives the audit-trail guarantee the project's tax-inspector discipline requires: bytes are never rewritten, so recomputing `sha256(blobs/<id>)` at any time can prove an attachment was not tampered with.
- Write-once byte storage and merge-on-re-ingest manifest semantics give additive, idempotent capture. Callers can safely re-issue `aeat attachments add <same-path>` with new links and the service will merge without double-counting.
- Tuple-typed linked IDs match the issue's stated types and align with the immutability discipline already used in `aeat.domain.financial.transactions`.
- Typing-only `Protocol` stubs for invoice/transaction references keep the attachment package from creating hard imports into sibling branches that are still in flight, mirroring the pattern established by `aeat.domain.financial.transactions._stubs`.
- Mounting at `aeat attachments` rather than `aeat financial attachments` matches the issue's explicit CLI wording and reflects the broader document-evidence scope (Gmail, Drive, contracts) that is not purely financial.
- Constraining the `metadata` escape hatch to `dict[str, str]` with non-empty keys preserves JSON round-trip safety and keeps the model a strict boundary even with the relaxation.

## Consequences

- The attachment service deliberately does not solve ingestion (Gmail/Drive pulls) or extraction (receipt OCR/LLM); those remain downstream work in `#80`, `#86`, and `#89`. The service only provides the evidence-layer primitives those pipelines will write through.
- Because `attachment_id` is derived from bytes, any byte-level change to a source file produces a new attachment; the old record is preserved for audit and garbage-collection is explicitly out of scope for this slice.
- Link semantics are additive in this issue: there is no unlinking and no delete command. Future work (a later TDP issue) can layer revocation on top of the current manifest model because links are stored as immutable tuples that a fresh model instance can shrink during a deliberate operation.
- The `metadata: dict[str, str]` escape hatch is a documented deviation from the project's strict Pydantic mandate. It is narrow (string-only values, non-empty keys, frozen on the model) and confined to the attachment surface. Broadening it further would require a follow-up ADR.
- The store's on-disk layout uses `blobs/` and `manifests/` subdirectories under the configured root. This is a stable persistence contract and must not be changed lightly once attachments are in use.
