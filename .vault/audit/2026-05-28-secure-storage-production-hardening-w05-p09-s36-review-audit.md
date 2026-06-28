---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-28-secure-storage-production-hardening-w05-p09-s36-side-store-inventory-audit]]'
---



# `secure-storage-production-hardening` W05.P09.S36 Code Review

No HIGH or CRITICAL findings were found.

S36-REVIEW-001 | MEDIUM | Ledger JSONL stores still lack a W05.P09 executable disposition owner
 The inventory correctly identifies `S36-JSON-002` in `src/aeat/application/ledger/_evidence.py` and `S36-JSON-003` in `src/aeat/application/ledger/_business_operation_invoice.py` as production bucket-local JSONL stores. Those rows are accurate, but their owner field is still a plan gap rather than an executable W05.P09 migration row or an accepted exception ADR owner. `W05.P09.S37`, `W05.P09.S38`, and `W05.P09.S39` cover evidence, inventory, and live stores; `W05.P09.S40` can cover retained exceptions, but no row currently names ledger evidence or business-operation invoice migration as a concrete W05.P09 follow-up. Before W05.P09 closes, add dedicated ledger migration rows or bind both stores to an accepted exception ADR through `W05.P09.S40`.

Resolution: addressed by adding follow-up plan rows `W17.P37.S424` for purchase invoice evidence JSONL migration and `W17.P37.S425` for payable and collectible business-operation invoice JSONL migration. The S36 inventory now points both ledger stores at those owners.

## Review Notes

The S36 inventory accurately covers the production bucket-local JSON and JSONL side stores found under the scoped application packages:

- `src/aeat/application/evidence/_service.py` persists evidence bundle manifests through `storage_path(settings.aeat_audit_dir / "evidence-bundles", bucket_id)`.
- `src/aeat/application/ledger/_evidence.py` persists purchase invoice evidence through `storage_path(settings.aeat_purchase_invoice_evidence_dir, bucket_id)`.
- `src/aeat/application/ledger/_business_operation_invoice.py` persists payable and collectible invoice records through `storage_path(settings.aeat_invoices_dir / kind.value, bucket_id)`.
- `src/aeat/application/inventory/_service.py` persists the inventory ledger document through `storage_path(settings.aeat_ledgers_dir / "inventory", bucket_id, extension=".json")`.
- `src/aeat/application/live/_verify.py` persists verify observations through `storage_path(settings.aeat_audit_dir / "live" / "verify", bucket_id)`.
- `src/aeat/application/live/_expedientes.py` and `src/aeat/application/live/_notifications.py` use `JsonlSnapshotRepository` with per-bucket files under the live audit directories.

No missing side stores were found in the requested scope. The already-secure dispositions are also supported by code evidence: `FiledDeclaracionObservationStore` saves filed-declaration artefacts, filed-declaration observations, and IVA wallet observations through the active secure-object repository, while Borrador 100, census snapshots, ledger classification rules, and IVA remote-state acquisition manifests use registered secure-object namespaces.

Operator-selected outputs such as the evidence bundle ZIP export and ledger command export path were not counted as production bucket-local JSON or JSONL side stores.
