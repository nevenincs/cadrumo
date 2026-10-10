---
tags:
  - '#reference'
  - '#mcp-parity'
date: '2026-10-10'
modified: '2026-10-10'
body_schema: 'body-v2'
body_hash: 'sha256:ef8a6489761de29be87c8a7557a61750a50bfe398d09283abec6959fa3c3138d'
related: []
---

# `mcp-parity` reference: `file exchange`

This record collects the code facts and owner rulings that bear on how files pass between an agent and Cadrumo. Every code locator is relative to the root of this repository, on branch `feature/tui`, read on 2026-10-10 by static analysis with nothing executed; the tree held other sessions' uncommitted work. Records named `2026-10-10-cadrumo-integration-...` belong to the vault of the cadrumo-agent repository and are cited by name. It states facts only and recommends nothing.

## Summary

- The owner ruled a plaintext per-profile folder beside the encrypted storage for the assistant, and one standing consent for a hosted model to read attached documents. Both rulings are narrower than an exchange folder for every agent (section 1).
- The storage taxonomy has a profile-keyed root beside the bucket and one plaintext area shared by all profiles, and names no exchange area (section 2).
- Reclaim, the custody inventory digest and profile deletion see only what is enrolled with them (section 3).
- Inbound operations differ in what they check and record: evidence add has no size ceiling and keeps two path strings; statement import has an optional digest hand-off; the reconciliation import records the path as its evidence reference (sections 4 and 5).
- The modelo export sink stages and publishes safely; the ledger export and the audit ZIP do not use it (section 6).

## 1. Owner rulings and requirements held in the cadrumo-agent vault

- The owner ruled where the assistant's per-profile folder lives: "Beside encrypted storage (Recommended)"; the option read "a plaintext folder keyed to the profile, next to its encrypted bucket; Cadrumo's profile deletion must be taught about it" (`2026-10-10-cadrumo-integration-owner-rulings-research`, first-hand answers, item 1).
- The owner ruled on sending attached documents to the hosted provider: "Yes, one standing consent"; the option read "the user consents once when enabling the assistant; Cadrumo's per-document consent rule has to be amended for the assistant" (same record, item 3).
- The owner said of attachments: "the conversation history has attachments. We have a storage for data ingest", with a backend interface for "uploading" and "adding files" (same record).
- The owner ruled first-hand in this repository's session: "agent can and should be able to call reconciliation records yes. It is important automation and user will always need to approve findings or review findings", and "all ledger ops must be possible to be operated by the agents" (`.vault/adr/2026-10-10-mcp-parity-admission-rulings-adr.md:222-224`, `:76-80`).
- `2026-10-10-cadrumo-integration-attachments-and-ingest-adr` requires three things of Cadrumo: open a file-taking operation to the tool path, "confine the paths such a session may name to its own root", and "compute the document's digest itself when it reads the file". It also binds that "The host keeps the original of every attachment outside the workspace, and that original is what Cadrumo ingests".
- `2026-10-10-cadrumo-integration-classification-and-reading-ownership-adr` requires that the served surface "never returns evidence bytes that are in Cadrumo's custody" and "a record of which values the assistant supplied, taken from the session and not from what the model writes". It leaves to Cadrumo "whether the assistant is withheld from the class of user for whom its record calls off-host reading unacceptable".
- `2026-10-10-cadrumo-integration-profile-data-root-adr` binds that "every file written by cadrumo-agent or by a provider process it starts lies under one root directory that belongs to one profile" and that "The Cadrumo host chooses and creates the root". It says Cadrumo "must enrol the new area in profile deletion, storage reclaim, its encrypted mirror and export".
- `2026-10-10-cadrumo-integration-deletion-and-retention-adr` binds that the root goes "when Cadrumo deletes the profile and when Cadrumo resets all profiles, and only then". `2026-10-10-cadrumo-integration-write-gate-adr` binds that "Whatever authorisation a Cadrumo write needs is enforced by Cadrumo".

## 2. Storage taxonomy and plaintext areas

- The taxonomy has four scopes, and the keystore is a profile-keyed root that sits beside `buckets/` and is never nested in the bucket (`src/cadrumo/core/storage_taxonomy.py:83-107`; `src/cadrumo/core/storage_taxonomy_locations.py:806-819`, `:1031-1041`).
- No taxonomy member names an exchange, inbox or agent area (`src/cadrumo/core/storage_taxonomy.py:207-321`).
- One plaintext operator area exists: `CONSOLE_WORKSPACE` at `<root>/workspace`. It is root-scoped, shared by all profiles, fixed, grouped as exports, excluded from the drift fingerprint and described as "not encrypted custody" (`src/cadrumo/core/storage_taxonomy_locations.py:134-145`).
- The native desktop host creates that workspace and uses it as the working directory of every terminal kind, after checking it is a real directory below the storage root (`native/desktop/src-tauri/src/environment.rs:355-356`; `native/desktop/src-tauri/src/terminal/mod.rs:63-88`; `native/desktop/src-tauri/src/terminal/console.rs:87-106`).
- Members with no settings field are not materialised by the storage tree; the bucket lifecycle provisions them per bucket (`src/cadrumo/core/storage_taxonomy_locations.py:1059-1061`, `:1091-1093`).

## 3. Reclaim, inventory and deletion

- Reclaim refuses the `state` and `exports` areas outright and refuses any target that is not root-scoped, link-like, or resolved outside the storage root (`src/cadrumo/application/storage_management/service.py:318-324`, `:366-371`, `:409-437`).
- The storage inventory resolves a profile-scoped member only for the active profile (`src/cadrumo/application/storage_management/service.py:533-536`).
- The custody inventory digest covers the profile capsule, which is the bucket directory, and nothing beside it (`src/cadrumo/adapters/persistence/storage/custody/_inventory.py:1`, `:28-34`, `:104-130`).
- Profile deletion is a journalled sequence of named states, each removing one named artefact, so a new sibling area needs its own step (`src/cadrumo/application/user_profile/custody_service.py:690-709`, `:751-804`, `:934`).

## 4. Inbound: evidence

- Evidence add expands and resolves the path, tests `is_file()`, and admits by extension only (`src/cadrumo/application/ledger/evidence.py:343-363`, `:529-560`).
- The evidence bytes are read whole with no size ceiling and stored under their SHA-256 in the encrypted attachment namespace (`src/cadrumo/adapters/persistence/storage/attachment.py:282-313`; `src/cadrumo/adapters/persistence/profile/purchase_invoice_evidence.py:159-172`).
- A planned digest, when supplied, is compared with the bytes of the single read that enters custody (`src/cadrumo/adapters/persistence/profile/purchase_invoice_evidence.py:160-172`; `src/cadrumo/application/ledger/evidence.py:752`, `:801-802`).
- Two path strings are persisted: the evidence record keeps the path as the operator typed it, and the attachment manifest keeps the resolved path as `source_reference` (`src/cadrumo/application/ledger/evidence.py:41-42`, `:519`, `:851`; `src/cadrumo/adapters/persistence/profile/purchase_invoice_evidence.py:179`).
- Evidence batch requires an absolute `source_directory`, sets no maximum on the number of sources, reads each file once to hash it and reads it again at work time under the planned digest (`src/cadrumo/application/ledger/evidence_ingestion_contracts.py:35-43`; `src/cadrumo/application/ledger/batch_ingest.py:779-783`, `:993-999`).

## 5. Inbound: statements, invoice books, reconciliation

- Statement import's digest hand-off is an optional request field; when present, a file whose parsed bytes differ is refused as `source_changed` (`src/cadrumo/application/ledger/import_operation.py:111-119`, `:455-463`).
- Only the terminal interface sets the hand-off, sending on apply the paths and digests the preview reported (`src/cadrumo/entrypoints/tui/runtime_ledger_import.py:89-104`).
- Statement import's public result carries per-file digests by index and a safe file name on refusal, and no path (`src/cadrumo/application/ledger/import_operation.py:122-128`, `:141-156`, `:197`, `:258-261`).
- A statement row's provenance stores the basename and the content digest, never an absolute path (`src/cadrumo/domain/transactions/raw_transaction.py:52-94`).
- The financial source guard refuses a symlink, a non-regular file and a source over 64 MiB; a request takes at most 128 files and 4096 rows (`src/cadrumo/adapters/inbound/financial/providers/base.py:75`, `:209-240`; `src/cadrumo/application/ledger/import_operation.py:53-54`).
- Invoice-book import takes an absolute `source_path` and a digest supplied by the caller (`src/cadrumo/application/invoices/catalogue_intake_contracts.py:25-39`).
- `modelo.reconcile.import` checks only that the path text is non-blank, bounded and free of NUL, parses the file in place, and uses the path string as the evidence reference (`src/cadrumo/application/modelo/reconciliation_import_operation.py:77-84`, `:119-125`, `:301-309`, `:328`; `src/cadrumo/application/modelo/reconciliation.py:403-433`).

## 6. Outbound: exports and the writer

- `modelo.export` requires an absolute `output_path` "resolved by the requesting frontend", journals it as "the operator's chosen destination", and defaults `replace_existing` to false (`src/cadrumo/application/modelo/work_export_contracts.py:27-29`, `:42`, `:52`, `:63-69`).
- The modelo export sink checks the path before any byte is written, stages under an unguessable sibling name opened with `O_EXCL`, discards the stage on any exit that does not publish, and can publish without replacing an existing file by hard link (`src/cadrumo/application/modelo/export_sink.py:66-116`; `src/cadrumo/core/atomic_write.py:108-129`, `:457-483`, `:550-609`).
- `ledger.export` uses a different writer and looser rules: no absolute rule on `output_path`, with CLI or TUI and a human session required (`src/cadrumo/application/ledger/export_operation.py:47-59`, `:236-242`); the standard write tier, which creates parent directories and replaces an existing file (`src/cadrumo/application/ledger/actions_export.py:110-119`; `src/cadrumo/core/atomic_write.py:150-163`); and the output path stored in the bucket event (`src/cadrumo/application/ledger/actions_export.py:140`).
- `modelo.audit.export` writes a ZIP directly at the caller's path, creating parent directories. As the operation calls it, no record payloads are passed, so the archive holds the manifest only (`src/cadrumo/application/modelo/audit_operation.py:89-96`, `:414-420`; `src/cadrumo/application/evidence/service.py:409-410`, `:434-445`).

## 7. Bytes in requests, consent and admission state

- A submission payload is bounded at 16 MiB and travels as base64 chunks; `ledger.classify.bulk` already carries CSV text in its request up to that bound (`src/cadrumo/application/runtime/submission_payload.py:14-18`; `src/cadrumo/application/ledger/bulk_classify_operation.py:60-71`).
- The accepted MCP record states "Source evidence bytes, passwords, keys and raw secure payloads do not enter MCP" (`.vault/adr/2026-09-26-mcp-purpose-authentication-adr.md:166`).
- Cadrumo's own off-host evidence read needs a stored evidence record and a per-invocation acknowledgement, and mints a consent proof bound to the source digest (`src/cadrumo/application/ledger/invoice_evidence_extract_operation.py:72-81`, `:219-235`).
- `cloud_evidence_upload` is the standing eligibility bar above that acknowledgement, and gestor mode bars it whatever the profile says (`src/cadrumo/application/user_profile/capabilities.py:14-22`, `:55`; `src/cadrumo/core/config.py:764-779`).
- Twenty-four rows of the recorded MCP decision table carry the file-exchange prerequisite (`src/cadrumo/application/operations/mcp_admission.py`, uncommitted when read).

## Not verified

- Whether the all-profile reset, the encrypted mirror, the sealed archive and the portable bundle walk directories beside the bucket. Only the profile-deletion step sequence was read.
- Whether any admitted export writes evidence bytes held in custody. Audit export and review-package build were read and do not; `profile.archive.export`, `user-profile.bundle-export`, the review-package exchange operations and the Google evidence packages were not traced.
- The path handling of `modelo.m145.export`, `modelo.spreadsheet.export`, `modelo.reconcile.export-xlsx`, `export.calculation-review-xlsx`, `live.borrador.100.import`, `user-profile.censo-file-import`, `modelo.filing_record.import` and `modelo.work.report_verify`. Only their request fields were listed.
- Size limits in the PDF parsers below evidence add and reconcile import.
- Windows behaviour of the hard-link publication and of handle-level reparse checks. Nothing was run.
- Whether adding a taxonomy scope touches any sentence of `2026-08-03-canonical-storage-management-adr` beyond those read (R11, R12, R25 and the reclaim rules).
- Where the hosted assistant's own per-profile root will sit in Cadrumo. No Cadrumo record or code declares it.
- What the person sees of a folder today. No surface lists one.
