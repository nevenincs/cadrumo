---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-28-secure-storage-production-hardening-w05-p09-s36-side-store-inventory-audit]]'
  - '[[2026-05-26-active-profile-storage-runtime-discovery-audit]]'
  - '[[2026-05-26-active-profile-storage-runtime-classification-closeout-audit]]'
  - '[[2026-05-28-secure-storage-production-hardening-w05-p09-s40-adr]]'
---

# `secure-storage-production-hardening` `W12.P24.S96` Side-Store Classification

## Scope

This audit classifies the application-side file-store surfaces named by `W12.P24.S96` so the runtime rollout does not leave bucket-local JSON, JSONL, ZIP, or live snapshot paths as untracked sensitive persistence backends.

The classification is grounded in the active-profile runtime discovery audit, the W05.P09.S36 side-store inventory, S37-S40 migration and exception reviews, the current application modules, and the W17 ledger JSONL follow-up rows.

## Classification Register

| Surface | Current implementation | Classification | Owner and required disposition |
| --- | --- | --- | --- |
| Evidence bundle manifests | `src/aeat/application/evidence/_service.py` persists `EvidenceBundle` through `EvidenceBundleRepository`, `SecureBoundRepository`, `APPLICATION_EVIDENCE_BUNDLE_NAMESPACE`, and `secure_object_repository_for_bucket`. | secure-object migration completed | Covered by W05.P09.S37. Keep as runtime-created secure-object storage; no bucket-local JSONL exception remains. |
| Evidence bundle ZIP export | `EvidenceBundleService.export()` writes only to an operator-supplied `output_path`, verifies first, refuses failed verification, requires `force_incomplete` for incomplete bundles, and writes `manifest.json` last. | export-only | Covered by W05.P09.S40 ADR. This is not a default bucket-local persistence backend. |
| Inventory ledgers | `src/aeat/application/inventory/_service.py` resolves `InventoryLedgerRepository` through `secure_object_repository_for_bucket` and the registered inventory namespace. | secure-object migration completed | Covered by W05.P09.S38. Keep runtime bucket mismatch refusal and namespace-registry sensitivity authority. |
| Purchase invoice evidence ledger records | `src/aeat/application/ledger/_evidence.py` still reads and writes `settings.aeat_purchase_invoice_evidence_dir / {bucket_id}.jsonl` through centralized `Settings` and `storage_path`. The payload includes source path, source digest, supplier, invoice number/date, taxable base, IVA rate, IVA amount, notes, and timestamps. | secure-object migration pending | Owned by `W17.P37.S424`. This is not an accepted plaintext exception and must migrate behind a runtime-created secure-object repository unless later implementation research produces explicit ADR-backed rejection. |
| Payable and collectible business-operation invoice records | `src/aeat/application/ledger/_business_operation_invoice.py` still reads and writes `settings.aeat_invoices_dir / {payable_invoice|collectible_invoice} / {bucket_id}.jsonl` through centralized `Settings` and `storage_path`. The payload includes counterparty identifiers, invoice numbers, dates, amounts, intracom fields, notes, and timestamps. | secure-object migration pending | Owned by `W17.P37.S425`. This is not an accepted plaintext exception and must migrate behind runtime-created secure-object repositories unless later implementation research produces explicit ADR-backed rejection. |
| Live verification observations | `src/aeat/application/live/_verify.py` persists `VerifyObservation` through `LIVE_VERIFY_OBSERVATION_NAMESPACE` and `secure_object_repository_for_bucket`. | secure-object migration completed | Covered by W05.P09.S39. Retain as encrypted bucket-scoped audit state. |
| Live expedientes snapshots | `src/aeat/application/live/_expedientes.py` uses `SecureSnapshotRepository`, `LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE`, and `secure_object_repository_for_bucket`. | secure-object migration completed | Covered by W05.P09.S39. No legacy JSONL snapshot store remains in the scoped implementation. |
| Live notifications snapshots | `src/aeat/application/live/_notifications.py` uses `SecureSnapshotRepository`, `LIVE_NOTIFICATIONS_SNAPSHOT_NAMESPACE`, and `secure_object_repository_for_bucket`. | secure-object migration completed | Covered by W05.P09.S39. No legacy JSONL snapshot store remains in the scoped implementation. |
| Shared live snapshot base | `src/aeat/application/live/_snapshot_base.py` implements `SecureSnapshotRepository` over registered namespace definitions and runtime-created secure-object repositories. | secure-object migration completed | Covered by W05.P09.S39. Remaining review caveats are list-time mismatch handling and stale comments, not plaintext side-store acceptance. |
| Borrador 100 and Censo live snapshots | W05.P09.S36 classified these as already secure-object backed registered live snapshot namespaces. | secure-object migration completed | Not a W12.P24 blocker; retain as registered secure-object snapshot families. |

## Disposition Rules

- No scoped sensitive bucket-local default store is accepted as plaintext in this audit.
- The only retained plaintext write boundary in the scoped application side-store set is explicit operator export to a caller-supplied path.
- The purchase invoice evidence and business-operation invoice JSONL stores remain open migration work. Their current use of centralized `Settings` and `storage_path` is necessary but not sufficient because they still form alternate sensitive persistence backends.
- No scoped store is classified as a rebuildable cache. The live snapshot and verification payloads are audit records, not disposable cache state.
- Remote mirror provider semantics remain owned by `W12.P24.S98`; the existing S98 evidence does not close the two application ledger JSONL stores.

## Closeout Criteria For Follow-Up Rows

- `W17.P37.S424` must either migrate purchase invoice evidence to a registered runtime-created secure-object repository or persist explicit ADR-backed rejection of migration.
- `W17.P37.S425` must either migrate payable and collectible business-operation invoices to registered runtime-created secure-object repositories or persist explicit ADR-backed rejection of migration.
- `W12.P24.S97` may treat evidence bundles, inventory ledgers, live verification, live expedientes, and live notifications as already migrated, but must not treat the two W17 ledger JSONL stores as closed.
- `W12.P24.S99` must prove retained export-only boundaries do not become default sensitive persistence backends and must include the two pending JSONL migrations once W17 implements or rejects them.

## Verification

- Reviewed `src/aeat/application/evidence/_service.py`, `src/aeat/application/inventory/_service.py`, `src/aeat/application/ledger/_evidence.py`, `src/aeat/application/ledger/_business_operation_invoice.py`, `src/aeat/application/live/_verify.py`, `src/aeat/application/live/_expedientes.py`, `src/aeat/application/live/_notifications.py`, and `src/aeat/application/live/_snapshot_base.py`.
- Reviewed W05.P09.S36 inventory and S37-S40 review/ADR evidence.
- Confirmed `W17.P37.S424` and `W17.P37.S425` remain the explicit migration owners for the two ledger JSONL stores.
