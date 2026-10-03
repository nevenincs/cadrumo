# Profile persistence for invoices, filings, and calculation evidence

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-018` · **Topic:** [Persistence and secure storage](../topics/persistence-and-secure-storage.md)

<!-- preserved:article -->
## Scope

This chunk contains 32 profile-persistence adapters for invoice intake, filing and calculation records, operational evidence, and replay protection. I read all assigned slices across nine bounded pages: 5,327 lines and 47,485 measured `o200k_base` proxy tokens. Static source review only; I did not run the application or tests, and the bundled authority references were not checked against current law.

## Invoice intake and source custody

The invoice catalogue is an encrypted FINANCIAL singleton bound to a profile bucket. Reads and writes reject records attributed to a different bucket; un-attributed records remain readable only when no bucket is known, such as an injected repository seam. The mutation API uses revision-guarded singleton writes to prevent concurrent invoice additions from overwriting one another. Catalogue creation can co-commit an invoice change with its bucket event: it reads both revisions, prepares the event write with its revision, commits the pair in one secure-object batch, and retries revision conflicts. Rate access is isolated behind an adapter that translates provider failures into the application contract. Bucket ownership checks (`src/cadrumo/adapters/persistence/profile/invoices.py`) Guarded invoice mutation (`src/cadrumo/adapters/persistence/profile/invoices.py`) Invoice and event co-commit (`src/cadrumo/adapters/persistence/profile/catalogue_creation.py`)

Evidence persistence separates a bucket-bound evidence catalogue from attachment bytes. The attachment adapter delegates byte and manifest custody to the encrypted attachment store; when a planned digest is supplied, ingestion reads and verifies the file bytes against it before storage. Confirmation and evidence bundles use secure-object ports, while confirmation has a dedicated attachment adapter that preserves ordinary missing/validation errors and translates storage failures. These modules do not themselves establish what the user is authorized to confirm; their contracts bind the persistence operation to the profile and typed evidence. Evidence revision and co-commit (`src/cadrumo/adapters/persistence/profile/purchase_invoice_evidence.py`) Attachment ingest and digest check (`src/cadrumo/adapters/persistence/profile/purchase_invoice_evidence.py`) Confirmation attachment boundary (`src/cadrumo/adapters/persistence/profile/invoice_confirmation.py`)

Filing drafts are encrypted FINANCIAL envelopes. Before writing or preparing a co-commit, the repository recomputes `draft_id` from modelo, period, taxpayer, authority snapshot, casilla values, and binding values, refusing a mismatch. One error message interpolates `profile_tax_id`; review its presentation/logging boundary so a rejected content address cannot expose that identifier in diagnostics. Filing records and work units are bucket-scoped singleton catalogues; their `mutate` APIs use revision guards, and filing records validate bucket ownership on both load and save. Verification reports are accepted only when their referenced calculation revision exists in the same store and has the same registry snapshot coordinates. Draft content-address validation (`src/cadrumo/adapters/persistence/profile/filing_drafts.py`) Tax ID in validation detail (`src/cadrumo/adapters/persistence/profile/filing_drafts.py`) Filing record bucket binding (`src/cadrumo/adapters/persistence/profile/modelos_filing.py`) Verification parent binding (`src/cadrumo/adapters/persistence/profile/modelos_verification_reports.py`)

## Calculation and lifecycle records

The modelo repositories persist work units, calculation revisions, filing records, edit receipts, verification reports, reconciliations, and a derived transaction-participation index. They apply the secure-object registry's namespace, classification and version contract. Calculation-revision reads revalidate stored revisions against the pinned authority, parent work units, and evidence coverage. Verification reports are cross-checked against local parent revisions on read and write. Lifecycle adapters for M036 and M145 bind record repositories and bucket-event history to a single bucket; their snapshot adapters support full-ID and unique-prefix lookup while reporting ambiguous prefixes. Reconciliation details are co-written with their bucket events. Calculation-revision load and authority checks (`src/cadrumo/adapters/persistence/profile/modelos_calculation.py`) M036/M145 record and event composition (`src/cadrumo/adapters/persistence/profile/m036_lifecycle.py`) Reconciliation co-commit (`src/cadrumo/adapters/persistence/profile/modelo_reconciliation.py`)

The participation index is a rebuildable cache linking transaction IDs to finalized revisions and filings. Its full replacement deletes stale rows and writes regenerated rows in one batch, with revision assertions over the source calculation, work-unit, and filing catalogues. Calculation observations keep official and pending-local sources in separate layers, bind entries to modelo/year/period/member coordinates, and run Modelo 303 ingress normalization against the bundled registry. Prorrata seeding fences both possible prior-year Modelo 303 source rows and the target register in one transaction; it also refuses a source snapshot from another database backend. Prorrata sector carry-forward and settlement rerun against the latest register on each compare-and-swap attempt. Percepciones replacement prepares and validates the whole new window before delegating a single transactional replace of stale and replacement rows. Atomic participation-index replacement (`src/cadrumo/adapters/persistence/profile/participation_index.py`) Observation ingress and layer behavior (`src/cadrumo/adapters/persistence/profile/calculation_observations.py`) Prorrata source revision fence (`src/cadrumo/adapters/persistence/profile/prorrata_register.py`) Sector lifecycle mutations (`src/cadrumo/adapters/persistence/profile/prorrata_register.py`) Window replacement adapter (`src/cadrumo/adapters/persistence/profile/percepciones_observations.py`) Shared transactional window implementation (`src/cadrumo/application/aggregation/observation_window.py`)

The inventory adapter similarly performs create, remove, movement, and closing-authority changes inside the guarded singleton mutation; movement valuation remains an application callback so it is rechecked on each retry. Smaller repositories store ordered classification rules, AUDIT justificante metadata, remote acquisition manifests, and profile path projections. M036 and M145 lifecycle adapters compose their record writes with bucket history, keeping lifecycle evidence and its record in one co-commit where the application asks for it. Guarded inventory changes (`src/cadrumo/adapters/persistence/profile/inventory.py`) Rule ordering (`src/cadrumo/adapters/persistence/profile/ledger_classification_rules.py`) M145 bucket-event composition (`src/cadrumo/adapters/persistence/profile/m145_communication_records.py`)

Other stores retain IVA compensation history, redacted live IVA acquisition manifests, AEAT justificante metadata, classification rules, and authenticated profile-path projections. These are typed encrypted records with storage errors translated at application boundaries. The profile also keeps an append-only recipient replay-nonce ledger: `mark_consumed` refuses an already-used nonce and retries revision conflicts up to 64 times, so concurrent decrypt attempts cannot both commit the same nonce when CAS works as intended. The ledger has no expiry or retention path and each append scans and rewrites its singleton tuple; it can grow indefinitely. That favors permanent replay detection, but long-term use should be checked for bounded storage and mutation cost. Replay nonce ledger and retry limit (`src/cadrumo/adapters/persistence/profile/recipient_replay_guard.py`) Single-use consume operation (`src/cadrumo/adapters/persistence/profile/recipient_replay_guard.py`)

## Assessment and limits

The strongest patterns are explicit bucket binding, revision-guarded singleton mutations, atomic batches for related catalogue/event updates, content-address checks for drafts and participation rows, and cross-record validation tying reports and calculations to their persisted parents. The main review points are the personal identifier embedded in a draft-validation exception and the replay ledger's unbounded append-only growth. Co-commit APIs often make `expected_revision_id` optional, so each caller that derives a whole singleton from a read must pass the exact observed revision; the concrete guarded mutation and lifecycle paths generally do so. Runtime transaction isolation, crash recovery, retention behavior under large profiles, and complete caller coverage remain unverified.

## Complete source coverage

All 32 assigned files were read in full; pages 1–9 covered every line in the manifest.

- catalogue_creation.py (335 lines) (`src/cadrumo/adapters/persistence/profile/catalogue_creation.py`)
- catalogue_reads.py (101 lines) (`src/cadrumo/adapters/persistence/profile/catalogue_reads.py`)
- confirmation_records.py (35 lines) (`src/cadrumo/adapters/persistence/profile/confirmation_records.py`)
- counterparty_establishment.py (85 lines) (`src/cadrumo/adapters/persistence/profile/counterparty_establishment.py`)
- evidence_bundles.py (89 lines) (`src/cadrumo/adapters/persistence/profile/evidence_bundles.py`)
- extraction_drafts.py (48 lines) (`src/cadrumo/adapters/persistence/profile/extraction_drafts.py`)
- filing_drafts.py (182 lines) (`src/cadrumo/adapters/persistence/profile/filing_drafts.py`)
- filing_history.py (87 lines) (`src/cadrumo/adapters/persistence/profile/filing_history.py`)
- inventory.py (360 lines) (`src/cadrumo/adapters/persistence/profile/inventory.py`)
- invoice_confirmation.py (110 lines) (`src/cadrumo/adapters/persistence/profile/invoice_confirmation.py`)
- invoice_source_resolver.py (36 lines) (`src/cadrumo/adapters/persistence/profile/invoice_source_resolver.py`)
- invoices.py (326 lines) (`src/cadrumo/adapters/persistence/profile/invoices.py`)
- iva_compensation_history.py (123 lines) (`src/cadrumo/adapters/persistence/profile/iva_compensation_history.py`)
- iva_remote_state.py (39 lines) (`src/cadrumo/adapters/persistence/profile/iva_remote_state.py`)
- justificante.py (69 lines) (`src/cadrumo/adapters/persistence/profile/justificante.py`)
- ledger_classification_rules.py (31 lines) (`src/cadrumo/adapters/persistence/profile/ledger_classification_rules.py`)
- m036_lifecycle.py (159 lines) (`src/cadrumo/adapters/persistence/profile/m036_lifecycle.py`)
- m145_communication_records.py (150 lines) (`src/cadrumo/adapters/persistence/profile/m145_communication_records.py`)
- modelo_reconciliation.py (88 lines) (`src/cadrumo/adapters/persistence/profile/modelo_reconciliation.py`)
- modelos_calculation.py (448 lines) (`src/cadrumo/adapters/persistence/profile/modelos_calculation.py`)
- modelos_edit_receipts.py (67 lines) (`src/cadrumo/adapters/persistence/profile/modelos_edit_receipts.py`)
- modelos_filing.py (355 lines) (`src/cadrumo/adapters/persistence/profile/modelos_filing.py`)
- modelos_verification_reports.py (306 lines) (`src/cadrumo/adapters/persistence/profile/modelos_verification_reports.py`)
- modelos_work_units.py (247 lines) (`src/cadrumo/adapters/persistence/profile/modelos_work_units.py`)
- notification_documents.py (53 lines) (`src/cadrumo/adapters/persistence/profile/notification_documents.py`)
- participation_index.py (276 lines) (`src/cadrumo/adapters/persistence/profile/participation_index.py`)
- percepciones_observations.py (218 lines) (`src/cadrumo/adapters/persistence/profile/percepciones_observations.py`)
- profile_path_values.py (35 lines) (`src/cadrumo/adapters/persistence/profile/profile_path_values.py`)
- prorrata_register.py (379 lines) (`src/cadrumo/adapters/persistence/profile/prorrata_register.py`)
- purchase_invoice_evidence.py (194 lines) (`src/cadrumo/adapters/persistence/profile/purchase_invoice_evidence.py`)
- recipient_replay_guard.py (220 lines) (`src/cadrumo/adapters/persistence/profile/recipient_replay_guard.py`)
- relation_binding_join.json (76 lines) (`src/cadrumo/adapters/persistence/profile/relation_binding_join.json`)
<!-- /preserved:article -->
