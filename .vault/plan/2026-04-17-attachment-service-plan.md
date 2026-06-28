---
tags:
  - "#plan"
  - "#attachment-service"
date: "2026-04-17"
modified: '2026-04-17'
related:
  - "[[2026-04-17-attachment-service-research]]"
  - "[[2026-04-17-attachment-service-adr]]"
  - "[[2026-04-14-transaction-catalogue-plan]]"
---

# `attachment-service` `phase-1` plan

Deliver issue `#76` as the content-addressed **Attachment** service at TDP step T3 (Enrich, see `#104`): new `aeat.domain.financial.attachments` subpackage with strict pydantic v2 models, a two-layer byte/manifest store, a root-level `aeat attachments` Typer CLI, additive settings wiring, Protocol-only stubs for invoice linking (`#75` is not on `main`), colocated tests, and mandatory verification/review artefacts.

## Proposed Changes

- Create the `aeat.domain.financial.attachments` subpackage with a public `__init__.py`, underscored private modules for enums, errors, models, store, service helpers, and typing stubs.
- Implement an `Attachment` pydantic model whose `attachment_id` equals the SHA-256 of the attachment bytes and whose `sha256`, `captured_at`, and linked-ID invariants mirror the existing `RawProvenance` discipline.
- Implement `AttachmentCatalogue` as an internal immutable container keyed by `attachment_id` for in-memory and round-trip convenience; persistence is per-attachment manifest, not a single catalogue blob.
- Implement an `AttachmentStore` that separates raw bytes (`<AEAT_ATTACHMENTS_DIR>/blobs/<sha256>`, write-once) from JSON manifests (`<AEAT_ATTACHMENTS_DIR>/manifests/<sha256>.json`, mutable as links are recorded).
- Implement service-level helpers (`add_attachment`, `load_attachment`, `list_attachments`) that hash bytes once, upsert the blob idempotently, merge any pre-existing links into the manifest, and return validated `Attachment` instances.
- Add an `AEAT_ATTACHMENTS_DIR` setting to `aeat.core.config.Settings` with the matching entry in `env/.env.example`.
- Mount the CLI at the root as `aeat attachments` (`add`, `list`, `show`), not nested under `aeat financial`, matching the issue's explicit wording.
- Keep invoice/transaction interoperability at typing level only through `_stubs.py` Protocols.
- Add colocated unit tests for models, catalogue, store (dedup + write-once + link merge + bytes/manifest separation), and CLI smoke coverage.

## Tasks

- `Phase 1: establish the attachment package surface`
  1. Create `aeat.domain.financial.attachments` with public `__init__.py` and private underscored modules.
  1. Define `AttachmentKind` and `AttachmentSource` as `StrEnum` values using the uppercase identifiers from issue `#76`.
  1. Define `AttachmentError` hierarchy inheriting from `aeat.core.errors.AeatError` (`AttachmentError`, `AttachmentValidationError`, `AttachmentPersistenceError`, `AttachmentNotFoundError`).
  1. Define `Attachment` as a strict frozen pydantic v2 model with:
     - 64-char lowercase hex validators on `attachment_id` and `sha256`.
     - A `model_validator` that enforces `attachment_id == sha256`.
     - Trimmed non-empty validators on `source_reference`, `mime_type`.
     - `bytes_size: int = Field(ge=0)`.
     - Timezone-aware validator on `captured_at`.
     - Linked-ID validators that reject blank strings, deduplicate, and preserve a deterministic ordering (insertion order).
     - A `metadata` validator that coerces the incoming mapping to a `MappingProxyType[str, str]`, rejecting empty keys and non-string values.
  1. Define `AttachmentCatalogue` wrapping `dict[str, Attachment]` with `__iter__`, `__len__`, `__contains__`, `get`, and a `from_attachments` class constructor that rejects duplicates.
  1. Add internal `Protocol` stubs (`SupportsTransactionId`, `SupportsInvoiceId`) in `_stubs.py`.
- `Phase 2: implement the byte + manifest store`
  1. Implement `AttachmentStore` as a strict frozen pydantic model with `ConfigDict(strict=True, frozen=True, extra="forbid")` (mirroring the transactions-subpackage `_STRICT_FROZEN` pattern) holding a single `root: Path`.
  1. Expose `blobs_dir` / `manifests_dir` derived properties. Creation is lazy inside each write helper; reads raise typed errors when missing.
  1. Implement `put_bytes(data: bytes) -> str`:
     - Hash `data` with SHA-256; compute the hex digest.
     - If `<blobs>/<digest>` exists: return digest unchanged (write-once).
     - Else: write atomically via a sibling tempfile + `os.replace`.
  1. Implement `read_bytes(sha256: str) -> bytes` (raises `AttachmentNotFoundError` if absent). A separate `open_bytes(sha256) -> BinaryIO` is not required for this slice; the issue's "BytesView (Protocol-shaped)" is satisfied by `bytes` (Python's `bytes` is itself a structural read-only sequence). Document the deliberate simplification in the module docstring.
  1. Implement `write_manifest(attachment)` with atomic tempfile + `os.replace` mirroring the transactions persistence pattern; implement `load_manifest(attachment_id)` via `Attachment.model_validate_json`.
  1. Implement `iter_manifests() -> Iterator[Attachment]` for the CLI `list` command. Iteration order is deterministic by sorted manifest filename so runs are stable across filesystems and OSes.
- `Phase 3: service helpers`
  1. Implement `add_attachment(store, *, path, kind, source, source_reference, mime_type, captured_at, link_transaction_ids=(), link_invoice_ids=(), metadata=None, notes="") -> Attachment`:
     - Read bytes from `path`. Any `OSError` is wrapped and re-raised as `AttachmentPersistenceError` (mirroring the transactions-subpackage error-translation contract); bare `OSError` must not leak to callers.
     - Call `store.put_bytes(...)` to get the digest.
     - Load any existing manifest for that digest; if present, union its link tuples with the caller-provided ones before constructing the new `Attachment`.
     - Construct and validate a fresh `Attachment` (with `attachment_id == sha256 == digest`, `bytes_size == len(bytes)`).
     - Persist the manifest via `store.write_manifest(...)` and return the attachment.
  1. Implement `load_attachment(store, attachment_id) -> Attachment` as a typed wrapper raising `AttachmentNotFoundError` when missing.
  1. Implement `list_attachments(store, *, linked_to: str | None = None) -> tuple[Attachment, ...]` iterating manifests and filtering by presence in either `linked_transaction_ids` or `linked_invoice_ids` when `linked_to` is supplied.
- `Phase 4: wire settings and CLI`
  1. Add `aeat_attachments_dir: Path = Field(default=PROJECT_ROOT / "var" / "financial" / "attachments", ...)` to `aeat.core.config.Settings`.
  1. Mirror the entry in `env/.env.example`.
  1. Add `src/aeat/entrypoints/cli/attachments.py` exposing a Typer `app` with three commands:
     - `add <path> [--kind] [--source] [--source-reference] [--mime-type] [--link-tx ...] [--link-invoice ...] [--metadata k=v ...] [--notes]` — infers sensible defaults (`source=LOCAL_FILE`, `source_reference=str(path)` when omitted, `mime_type` via `mimetypes.guess_type`), uses `datetime.now(UTC)` for `captured_at`, and prints the persisted manifest JSON on success. `--metadata` parsing rules: each value must contain exactly one `=` separator; the key is the left side (trimmed, non-empty) and the value is the right side (kept verbatim, may contain `=`); duplicate keys within one invocation exit with code 2.
     - `list [--linked-to <id>] [--kind <kind>]` — tab-separated tabular listing sorted by `captured_at` then `attachment_id`.
     - `show <attachment_id>` — prints the manifest JSON.
  1. Register the sub-app in `src/aeat/entrypoints/cli/__init__.py` as `aeat attachments`.
- `Phase 5: verify and document execution`
  1. Add colocated `@pytest.mark.unit` tests under `src/aeat/domain/financial/attachments/`:
     - `test_models.py` — hash mismatch rejection, invalid sha256, naive `captured_at`, empty linked IDs, duplicate linked IDs dedup, invalid metadata shapes (empty key, non-string value).
     - `test_catalogue.py` — construction, duplicate detection, JSON round-trip.
     - `test_store.py` — dedup (same bytes → same id), write-once (pre-existing blob not overwritten), manifest round-trip, link merging on re-ingest.
     - `test_cli.py` — `add` / `list [--linked-to]` / `show` smoke via `CliRunner`, using a temp directory injected via `AEAT_ATTACHMENTS_DIR`.
  1. Run `just lint && just typecheck && just test && just hooks` on Windows. Fix root causes rather than adding skips.
  1. Write exec step records and phase summary in `.vault/exec/2026-04-17-attachment-service/`.
  1. Run the mandatory code review via `vaultspec-code-review` persona and persist the review artefact.
  1. Prepare the commit (Conventional Commits: `feat(financial): add attachment service`) and the PR body with vaultspec annotations. Do not push until all local gates pass.

## Parallelization

Sequential execution is safest here because the package surface, store, service helpers, CLI wiring, and tests share a tight set of invariants (the `attachment_id == sha256` equality, the byte/manifest separation, and the link-merge semantics). The only safe overlap is writing exec-record notes while the next phase's tests are executing. Each phase's tests should run before moving to the next phase, but the final `just`-gate pass is a single combined run at the end.

## Verification

- `Attachment` round-trips through `model_dump_json` / `model_validate_json` with tuple ordering preserved.
- `Attachment.model_validate(...)` rejects any payload where `attachment_id != sha256`.
- `Attachment` accepts only 64-char lowercase hex `sha256` / `attachment_id` and only timezone-aware `captured_at`.
- Linked-ID tuples are deduplicated on validation (equal inputs collapse; ordering is deterministic).
- `metadata` with an empty key or a non-string value is rejected.
- `AttachmentCatalogue.from_attachments([a, a])` raises on the duplicate.
- `AttachmentStore.put_bytes(data)` returns the same digest and leaves the existing blob byte-identical on a repeated call (write-once).
- `add_attachment` called twice on the same path with different `--link-tx` values produces a single on-disk blob, a single manifest file, and a union of both link sets in the final manifest.
- `AttachmentStore.put_bytes(data)` records `bytes_size == len(data)` on the resulting `Attachment`, and the on-disk blob size equals `len(data)` byte-for-byte.
- A blob file written without an accompanying manifest is not surfaced by `iter_manifests()` or `list_attachments(...)`; orphan bytes are ignored until a corresponding manifest exists.
- `list_attachments(store, linked_to="tx-1")` returns only manifests whose `linked_transaction_ids` or `linked_invoice_ids` contain `"tx-1"`.
- `aeat attachments add`, `list`, and `show` are reachable from the root CLI and behave correctly under `CliRunner` with `AEAT_ATTACHMENTS_DIR` injected.
- `tests/test_config.py` passes — the new `aeat_attachments_dir` field has a matching line in `env/.env.example`.
- `just lint && just typecheck && just test && just hooks` pass cleanly on Windows for the final tree.

## Explicit Plan Review

- **Scope check against issue `#76`:** The plan covers the new `aeat.domain.financial.attachments` subpackage, the content-addressed byte/manifest store, the `aeat attachments` CLI, the `AEAT_ATTACHMENTS_DIR` setting, Protocol stubs for the invoice link, and colocated tests. It excludes Gmail/Drive ingestion (`#80`), receipt extraction (`#86`), matching (`#89`), unlinking/deletion, and any submission-layer work.
- **TDP check against issue `#104`:** The plan keeps the work at T3 Enrich, preserves content-addressed provenance invariants (byte-level `sha256` = `attachment_id`, write-once blobs, mutable manifests), and avoids reaching into T4/T5 classification/persistence ownership.
- **Sibling-branch check:** The plan does not import from `src/aeat/domain/financial/invoices/` (not on `main`), does not touch `src/aeat/adapters/outbound/aeat/export/`, and only adds one additive setting to `src/aeat/config.py`. Transaction linking is kept to opaque `str` identifiers.
- **Convention check against active repo instructions:** The plan stays inside `src/aeat/`, uses strict pydantic v2, `StrEnum`, pytest-only tests (`@pytest.mark.unit`), additive settings changes, and the canonical `AEAT_LIVE_TESTS_ENABLED` contract (live tests not required for this slice).
- **Repository policy check:** No GitHub Actions work is introduced; no `.github/workflows/release-please.yml` file is added. Local gates remain authoritative.
- **`metadata` escape hatch:** The plan enforces `dict[str, str]` with empty-key rejection and is internally consistent with the ADR's narrow justification.
- **`BytesView` simplification:** The plan uses `bytes` for the read return and documents the deliberate simplification, per the ADR audit's non-blocking observation.
- **Review outcome:** Approved for execution under the user's explicit instruction to run the full pipeline without pausing for plan approval.
