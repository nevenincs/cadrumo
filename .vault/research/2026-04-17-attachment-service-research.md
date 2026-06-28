---
tags:
  - "#research"
  - "#attachment-service"
date: "2026-04-17"
modified: '2026-04-17'
related:
  - "[[2026-04-14-transaction-catalogue-research]]"
  - "[[2026-04-14-transaction-catalogue-adr]]"
  - "[[2026-04-14-transaction-catalogue-plan]]"
---

# `attachment-service` research: `tdp-t3-evidence-layer`

This research grounds issue `#76` at the T3 Enrich step of the Transaction Data Pipeline (TDP, `#104`). The feature must deliver a typed, content-addressed **Attachment** service that binds supporting documents (invoice PDFs, Gmail messages, Drive documents, receipts, contracts, metadata blobs) to `Transaction` and/or `Invoice` records. Every casilla value the system eventually justifies must trace back through a provenance chain that terminates at one or more attachments.

## Findings

### Upstream contract already on main

- `aeat.domain.financial.transactions.Transaction` (`#74`) is on `main`. It exposes a `transaction_id` foreign-key slot callable from attachment records. Attachments must treat that identifier as opaque and hold references as plain strings validated at typing level only.
- `aeat.domain.financial.providers.RawTransaction` (`#73`) carries byte-level provenance via `RawProvenance` with a 64-character lowercase SHA-256 discipline and timezone-aware `ingested_at`. The attachment service must mirror that discipline for file hashes and `captured_at` timestamps.
- `aeat.domain.financial.invoices/` (issue `#75`) is **not yet on main**. Invoice foreign keys must be modelled as plain `str` runtime fields with internal `Protocol` placeholders for typing only.

### Content-addressed identity

- The issue mandates `attachment_id = stable hash of content`. The safest, simplest mapping is `attachment_id == sha256(bytes)` — both fields are stored, but they are required to be equal so the catalogue key is always consistent with the byte-store key.
- Two ingests of the same file therefore produce the same `attachment_id`, which naturally collapses duplicate uploads into a single manifest update (dedup is a consequence of content addressing, not a separate code path).
- Because hashing is deterministic, re-ingesting a file whose manifest has drifted — for example, one that has been re-linked to a new transaction since last upload — must merge links rather than rewrite the manifest from scratch.

### Byte store vs manifest store separation

- The issue scope is explicit: *"`AttachmentStore` — content-addressed local storage of attachment bytes under `var/financial/attachments/<sha256>`"* and *"`Attachment` instances are persisted as JSON manifests under `var/financial/attachments/` separate from the bytes."*
- This separation is a deliberate audit guarantee: raw bytes are never rewritten once stored (write-once), while the JSON manifest can evolve as new links are recorded. A future audit can re-hash the byte file and compare against the manifest's `sha256` to detect corruption.
- A flat namespace with a shared parent directory is the simplest layout that satisfies the mandate:
  - Bytes live at `<AEAT_ATTACHMENTS_DIR>/blobs/<sha256>` (extensionless; MIME authoritative on the manifest).
  - Manifests live at `<AEAT_ATTACHMENTS_DIR>/manifests/<sha256>.json` (one manifest per content hash).
- The `blobs/` and `manifests/` subdirectories cannot collide with 64-character hex filenames, so coexistence under the same root is safe.

### Linking semantics

- The issue specifies `linked_transaction_ids: tuple[str, ...]` and `linked_invoice_ids: tuple[str, ...]`. Tuples mean: ordered, immutable, deduplicated by the model on validation.
- Attachments are many-to-many with transactions and invoices. A single receipt PDF can justify a deposit and a later refund; a single invoice PDF can document both its issued invoice record and an associated transaction.
- Re-linking an attachment (via `add` with different `--link-*` flags, or via a future `link` command) must **merge** the new IDs into the existing tuple without duplication and without dropping prior links. This is part of the "every casilla value traces back to one or more attachments" guarantee.

### CLI surface precedent

- Root-level command groups like `aeat inbox`, `aeat manual`, and `aeat casillas` all host their own Typer sub-apps at the top of the CLI tree.
- Financial-pipeline commands live under `aeat financial` (e.g. `aeat financial txs`, `aeat financial ingest`). The issue body explicitly names the attachment commands as `aeat attachments ...`, i.e. a **top-level** command group parallel to `aeat financial`.
- Given the issue is authoritative, the CLI surface should be mounted at the root as `aeat attachments`, not nested under `aeat financial`. The attachment service's scope (PDFs, Gmail messages, Drive documents, receipts, contracts, metadata blobs) legitimately straddles the financial track and broader document-evidence needs, so a top-level command group is the correct semantic home.

### Metadata escape hatch

- The issue explicitly flags `metadata: dict[str, str]` as an "escape hatch — bare-string-only, justified in ADR; only allowed for free-form provider metadata". This is a conscious relaxation of the project's Pydantic mandate for boundary-crossing structures.
- The ADR must restate the justification: provider-specific metadata (Gmail message headers, Drive revision IDs, EXIF dumps) is intentionally heterogeneous and not worth enumerating. Constraining values to `str` preserves JSON round-trip safety; keys remain free-form identifiers.
- Validation must still forbid empty keys and enforce string types (not dicts-of-dicts, not bytes) to keep the escape hatch from becoming a smuggling channel for arbitrary nested shapes.

### Sibling-branch boundary constraints

- `src/aeat/domain/financial/invoices/` is not on `main` (`#75`). Typing-only `Protocol` stubs in a private `_stubs.py` describe the invoice-reference shape without hard-importing unmerged siblings.
- `src/aeat/domain/financial/transactions/` *is* on `main` (`#74`) and exposes stable `Transaction`/`transaction_id` surfaces; attachment linking can reference those types at typing level but the service only stores the identifier string at runtime to avoid tight coupling.
- `src/aeat/adapters/outbound/aeat/export/` is out of scope entirely.
- `src/aeat/config.py` accepts one additive setting (`AEAT_ATTACHMENTS_DIR`).

### Verification strategy

- Colocated unit tests under `src/aeat/domain/financial/attachments/` match the repo's financial-subpackage style (see `aeat.domain.financial.transactions`, `aeat.domain.financial.providers`).
- Strongest regression checks:
  - Content-addressed deduplication: storing the same bytes twice yields the same `attachment_id` and the same on-disk byte path.
  - Link-merge idempotence: adding an attachment a second time with a new transaction link must merge, not replace.
  - Manifest round-trip: `model_dump_json` → `model_validate_json` must preserve every field including tuple ordering.
  - Bytes/manifests separation: a manifest exists without byte content never corrupts the store; a byte file without manifest never leaks through `list`/`show`.
  - CLI coverage for `add`, `list --linked-to`, and `show <id>`.
- Live tests are not required for this slice; the service operates purely on local filesystem state. No Google Workspace fixtures are touched.

## Non-goals

- **Gmail/Drive ingestion:** `#80` (Google Workspace ingestion provider) will produce attachments via this service; the reverse-adapter code belongs to that issue.
- **Receipt extraction:** `#86` (LLM receipt PDF extractor) will consume attachments but lives downstream of T3.
- **Receipt-to-transaction matching:** `#89` owns the matching engine; the attachment service only supplies the evidence layer.
- **Unlinking:** removal of links and attachment deletion are deferred; the current scope is additive capture.
