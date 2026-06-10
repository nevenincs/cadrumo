---
tags:
  - '#research'
  - '#ledger-evidence-enforcement'
date: '2026-06-10'
related: []
---



# `ledger-evidence-enforcement` research: `Ledger evidence enforcement and secure-byte custody`

This is the C2 cluster of the ledger-evidence campaign: manual-transaction
evidence attachment and the custody guarantees around it. The campaign's binding
invariant is that every evidence record must carry encrypted bytes in the
per-profile bucket-scoped secure-object store; link-only evidence is forbidden.
This document inventories what already works, names the single byte-custody leak
that violates the invariant, and surveys the gap between the working code and
the documented operator surface so the sibling ADR can settle five decisions.

The scope is deliberately narrow: the manual-ledger evidence-attachment path
(add-time and post-hoc), the byte-storage substrate underneath it, the link
recording path, and the verify-time advisory surface. It does not cover the
purchase-invoice OCR pipeline internals, the import-bank-statement parser, or the
modelo export evidence-bundle surface (the C-cluster siblings own those).

## Findings

### Add-time evidence attachment already works end-to-end

`ManualLedgerTransactionCommand` carries two evidence references:
`purchase_invoice_evidence_id` (a single id) and `attachment_ids` (a tuple). The
CLI `aeat app ledger add` exposes both as `--purchase-invoice-evidence-id` and
repeatable `--attachment-id` options (`src/aeat/entrypoints/cli/_ledger.py`).
`create_manual_transaction` (`src/aeat/application/ledger/_actions_manual.py`)
calls `_verify_evidence_references` before persisting, which confirms the
purchase-invoice evidence record exists, belongs to the same bucket, and is in
the expected lifecycle state, and that every attachment id resolves in the
attachment store. So an operator can attach evidence *at creation time*, and the
references are integrity-checked. The same verifier runs on the update path
(`update_manual_transaction` / `_prepare_manual_transaction_update`).

A separate post-hoc verb, `aeat app ledger attach`
(`attach_manual_transaction_evidence` in the same module), lets an operator add
evidence to an already-created transaction. It is a thin wrapper over
`update_manual_transaction_fields`, so it inherits the same reference
verification. Each evidence linkage emits a typed bucket event
(`PURCHASE_INVOICE_EVIDENCE_ATTACHED`/`REPLACED`/`DETACHED`, `ATTACHMENT_LINKED`/
`ATTACHMENT_REMOVED`) and records a `TransactionEvidenceProvenanceEntry` on the
transaction. Evidence linkage is therefore already audit-cross-referenced (a C7
contract point).

### Byte storage is already encrypted and bucket-scoped

The `AttachmentStore` adapter
(`src/aeat/adapters/persistence/storage/attachment.py`) routes every byte write
— `put_file`, `put_bytes`, `write_manifest` — through `SecureObjectRepository`
bound to the active bucket via `secure_object_repository_for_active_bucket()`.
Blobs land in `ATTACHMENT_BLOB_NAMESPACE`; manifests in
`ATTACHMENT_MANIFEST_NAMESPACE` (both declared in `_namespace_registry.py`). Blob
payloads are wrapped behind a fixed envelope prefix so the stored `payload_hash`
is not the bare content digest (a content-presence-oracle mitigation). Reads
re-hash and verify; an un-prefixed payload is refused as corruption, not read
tolerantly.

Purchase-invoice evidence has its own encrypted store:
`PurchaseInvoiceEvidenceRepository` (a `SecureBoundRepository`) over
`LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE`
(`src/aeat/application/ledger/_evidence.py`). `PurchaseInvoiceEvidenceService.add`
SHA-256-hashes the source file and persists a bucket-local encrypted catalogue;
input is restricted to PDF and image media kinds, and a non-PDF/non-image source
is refused with a typed `PurchaseInvoiceEvidenceInputError`. So both evidence
families — generic attachments and purchase-invoice evidence — already satisfy
the secure-storage invariant for *file* inputs.

### The single byte-custody leak: `add_link_attachment`

`add_link_attachment` (`src/aeat/domain/attachments/_service.py`) is the one path
that violates the campaign invariant. Given a Gmail / Drive / URL reference it
stores the *reference text* as the payload (`mime_type = "text/uri-list"`,
`put_bytes(source_reference.encode(...))`) and never fetches the remote document.
The CLI verb `aeat app ledger doclink`
(`src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`) is its sole caller: it maps
the `--source` (`DocumentLinkSource`: gmail / google_drive / url) to an
`AttachmentKind`, calls `add_link_attachment`, then links the resulting
attachment id to the transaction via `attach_manual_transaction_evidence`.

The result is an attachment manifest that *looks* like evidence (it carries an
id, links to the transaction, emits audit events) but whose stored bytes are
merely a URL string. The actual invoice/receipt never enters secure storage; if
the linked Gmail message or Drive file is later deleted or access is revoked, the
"evidence" is an unresolvable pointer. This is the locked-decision target: a
record that cannot obtain the document bytes must be refused, not stored as a
link.

### A scope-aware fetch adapter already exists

Crucially, the fetch-and-refuse machinery the locked decision needs is *already
implemented*: `resolve_document_link`
(`src/aeat/adapters/outbound/google/_document_link_resolver.py`) takes an
`AttachmentSource` + reference + Google OAuth credentials and returns the fetched
bytes. Its posture is exactly the one the campaign wants:

- `GOOGLE_DRIVE` link whose file id is reachable under the granted `drive.file`
  scope: fetches and returns the bytes (`_download_drive_file`).
- `GOOGLE_DRIVE` file outside `drive.file` (403/404): raises
  `OutboundStoragePermissionError` naming the required `drive.readonly` scope.
- `GMAIL` link: raises `OutboundStoragePermissionError` naming the required
  `gmail.readonly` scope (the integration deliberately does not request it).
- `URL` link: raises `OutboundStoragePermissionError` — an arbitrary external URL
  is outside the granted scope and requires `drive.readonly` or manual download.

So the byte-custody fix is mostly a *wiring* change: the doclink path should call
`resolve_document_link` and then `add_attachment` (the byte-bearing path, which
fetches/stores and writes a manifest with the real `sha256` and `mime_type`),
keeping the link reference as manifest metadata. When `resolve_document_link`
raises a permission/validation error, the doclink verb must refuse with an
actionable message rather than fall back to storing a link.

### No evidence-presence advisory exists on the verify path

`verify_modelo_revision` (`src/aeat/application/modelo/_verification_actions.py`)
already aggregates findings from registry, clean-state, provenance, and workflow
gates, and the calculate path already surfaces non-blocking
`CalculationSourceDiagnostic` advisories (the unconsumed-declarable-IVA advisory
is the worked precedent: `unsupported_ledger_iva_observations` →
`source_advisories` JSON list / `ADVISORY:` CLI line). But nothing ties *evidence
presence* to a transaction's economic role. A positive-amount business expense
(OUTGOING) with no purchase invoice, or a cuota-bearing income (INCOMING) with no
issued invoice, files silently with no evidence and no operator alert. This is
the gap the `no-silent-under-declaration` discipline asks us to close with an
advisory (not a hard block, because legitimately evidence-free cases exist).

### Documentation presents evidence as post-hoc only

`docs/how-to/ledger-evidence.md` and `docs/how-to/import-bank-statements.md`
present the `attach`/`evidence` verbs as the way to add evidence after the fact;
the add-time `--purchase-invoice-evidence-id` / `--attachment-id` flow is
undocumented. The primary documented path should be add-time attachment, with
post-hoc `attach` as the secondary flow. This is a user-facing docs change and
rides the `vaultspec-documentation` workflow, not this ADR.

### Cross-cluster contract notes

- **C4 (invoices):** an invoice *is* a kind of evidence, but the `invoice`
  record and `purchase_invoice_evidence` remain distinct source kinds and
  distinct stores. Do not merge them; the campaign keeps the two evidence
  families separate.
- **C7 (audit cross-reference):** evidence linkage already emits typed bucket
  events and records provenance entries. The byte-custody fix must preserve this
  cross-referencing — the fetched-and-encrypted attachment still emits
  `ATTACHMENT_LINKED` and records a provenance entry exactly as the link path
  does today.

### Secure-storage gate (campaign invariant audit)

All three evidence stores ride encrypted bucket-scoped secure-object namespaces:
attachment blobs (`ATTACHMENT_BLOB_NAMESPACE`), attachment manifests
(`ATTACHMENT_MANIFEST_NAMESPACE`), and purchase-invoice evidence
(`LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE`). No plaintext financial document
sits on disk outside these namespaces. The *sole* leak is `add_link_attachment`,
which stores a pointer instead of the document; closing it (fetch-and-encrypt or
refuse) brings the entire evidence surface under the invariant.

### Relevant prior decisions

`2026-04-17-attachment-service-adr` (the attachment store),
`2026-05-04-calculation-authority-evidence-tiering-adr` (evidence tiers on the
calculation authority), and `2026-06-03-modelo-export-evidence-parity-adr`
(evidence bundled into exports) frame the surrounding evidence model. Governing
rules: `aeat-safety-legal-gates` (no silent under-evidenced filing),
`no-silent-under-declaration` (advisory-not-block discipline),
`aeat-calculation-grounding` (provenance through boundaries),
`ledger-derived-revisions-bundle-evidence` (revisions carry their evidence), and
`no-legacy-compatibility` (delete the link-only path, do not bridge it).
