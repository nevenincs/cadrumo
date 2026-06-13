---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
---

# `secure-storage-production-hardening` W05.P09.S36 side-store inventory

## Scope

This inventory covers production application-side bucket-local JSON and JSONL persistence under the evidence, ledger, inventory, live, and snapshot surfaces named by `W05.P09.S36`. It excludes tests, fixture files, bundled regulatory resources, operator-selected exports, and already-encrypted secure-object repositories except where they clarify that a suspected side store is already migrated.

The architecture backing is the accepted secure-storage hardening ADR requirement that governed sensitive bucket-local JSON or JSONL stores either migrate behind runtime-created secure-object repositories or receive an explicit accepted exception with classification, threat model, retention, export intent, and migration or retirement policy.

## Method

The codebase pass used `rg` against production modules for `storage_path(`, `read_text(`, `write_text(`, `.json`, `.jsonl`, `JsonlSnapshotRepository`, `output_root`, and settings directory roots. The candidate set was then checked manually against the implementing service classes and the namespace registry so already-secure paths were not counted as plaintext side stores.

## Bucket-local JSON and JSONL stores

| id | implementation | root and format | payload | sensitivity | owner |
| --- | --- | --- | --- | --- | --- |
| S36-JSON-001 | `src/aeat/application/evidence/_service.py` | `settings.aeat_audit_dir / "evidence-bundles" / {bucket_id}.jsonl` | `EvidenceBundle` manifests with work-unit ids, object refs, digests, filing/calculation refs, verification state, and notes | audit plus financial linkage | `W05.P09.S37` migration target |
| S36-JSON-002 | `src/aeat/application/ledger/_evidence.py` | `settings.aeat_purchase_invoice_evidence_dir / {bucket_id}.jsonl` | `PurchaseInvoiceEvidence` records with source path, source digest, supplier, invoice number/date, taxable base, IVA rate, IVA amount, and notes | financial evidence | `W17.P37.S424` migration target |
| S36-JSON-003 | `src/aeat/application/ledger/_business_operation_invoice.py` | `settings.aeat_invoices_dir / {payable_invoice|collectible_invoice} / {bucket_id}.jsonl` | payable and collectible business-operation invoice records with counterparty identifiers, invoice numbers, dates, amounts, intracom fields, and notes | financial ledger | `W17.P37.S425` migration target |
| S36-JSON-004 | `src/aeat/application/inventory/_service.py` | `settings.aeat_ledgers_dir / "inventory" / {bucket_id}.json` | `InventoryLedgerDocument` containing actividad/year ledgers, movements, valuation method, quantities, taxable bases, VAT rates, and costs | financial ledger | `W05.P09.S38` migration target |
| S36-JSON-005 | `src/aeat/application/live/_verify.py` | `settings.aeat_audit_dir / "live" / "verify" / {bucket_id}.jsonl` | `VerifyObservation` rows for NIF-IVA and TGVI checks with NIF, verdict, expected verdict, raw evidence locator, and timestamps | identity and audit | `W05.P09.S39` migration target |
| S36-JSON-006 | `src/aeat/application/live/_expedientes.py` through `JsonlSnapshotRepository` | `settings.aeat_audit_dir / "live" / "expedientes" / {bucket_id}.jsonl` | `PersistedExpedientesSnapshot` records containing declaration-register rows, source URL, capture time, and persisted time | financial and audit | `W05.P09.S39` migration target |
| S36-JSON-007 | `src/aeat/application/live/_notifications.py` through `JsonlSnapshotRepository` | `settings.aeat_audit_dir / "live" / "notifications" / {bucket_id}.jsonl` | `PersistedNotificationsSnapshot` records containing remote notification rows, source URL, capture time, and persisted time | identity and audit | `W05.P09.S39` migration target |

## Operational exports and already-secure surfaces

| surface | disposition |
| --- | --- |
| Evidence bundle ZIP export in `src/aeat/application/evidence/_service.py` | Operator-selected export path. It writes `manifest.json` last and verifies before export. It should be covered by `W05.P09.S40` if retained as an explicit export exception, but it is not a bucket-local default side store. |
| Filed declaration observations and artefacts in `src/aeat/application/live/__init__.py` via `FiledDeclaracionObservationStore` | Already encrypted through the active secure-object backend. The `output_root` argument is retained for report/logical path compatibility; the adapter returns `db://secure_objects` logical paths and saves in registered filed-declaration namespaces. |
| IVA wallet observations in `src/aeat/application/live/__init__.py` via `FiledDeclaracionObservationStore` | Already encrypted through the active secure-object backend and registered IVA wallet observation namespace. |
| IVA remote-state acquisition manifests in `src/aeat/application/live/__init__.py` | Already encrypted through `IvaRemoteStateAcquisitionManifestRepository` and the registered live IVA remote-state acquisition namespace. |
| Borrador 100 and census snapshot repositories in `src/aeat/application/live/_borrador_100.py` and `src/aeat/application/live/_censo.py` | Already secure-object backed, registered as live snapshot namespaces, and not plaintext side-store blockers for `W05.P09.S39`. |

## Plan implications

`W05.P09.S37`, `W05.P09.S38`, and `W05.P09.S39` cover evidence bundles, inventory ledgers, and live snapshot/verify stores. The ledger evidence and business-operation invoice JSONL stores are named by `W05.P09.S36` and are now tracked by the later `W17.P37.S424` and `W17.P37.S425` follow-up rows so canonical plan ordering remains valid.

The immediate migration order should be:

1. Migrate `S36-JSON-001` behind a runtime-created secure-object repository.
2. Migrate `S36-JSON-004` behind a runtime-created secure-object repository.
3. Migrate `S36-JSON-005`, `S36-JSON-006`, and `S36-JSON-007` behind runtime-created secure-object repositories.
4. Execute `W17.P37.S424` and `W17.P37.S425`, or replace them with explicit accepted exception ADR coverage if implementation research rejects migration.
