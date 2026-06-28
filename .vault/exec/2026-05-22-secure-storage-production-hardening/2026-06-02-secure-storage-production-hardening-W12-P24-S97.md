---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S97'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-w12-p24-s96-side-store-classification-exec]]'
  - '[[2026-06-02-secure-storage-production-hardening-W17-P37-S424]]'
  - '[[2026-06-02-secure-storage-production-hardening-W17-P37-S425]]'
---

# `secure-storage-production-hardening` `W12.P24.S97`

## Description

- Reconciled the S96 side-store classification after the W17 ledger migrations landed.
- Verified evidence bundles, inventory ledgers, purchase invoice evidence, business-operation invoices, live verification observations, live expedientes snapshots, live notification snapshots, Borrador 100 snapshots, and Censo snapshots route durable bucket-local state through runtime-created secure-object repositories.
- Preserved evidence bundle ZIP export as the only retained plaintext boundary in the scoped set, limited to operator-directed output paths.
- Removed stale purchase-invoice evidence wording that still referenced legacy bucket-local JSONL storage.

## Changed Surface

- `src/aeat/application/ledger/_evidence.py`

## Outcome

Implemented and reviewed.

The sensitive bucket-local side stores named by S96 are now either migrated to runtime-created secure-object repositories or retained only as explicit operator-directed export output. No scoped application module retains a default JSON or JSONL sensitive side-store path.

## Verification

- `uv run --no-sync pytest -q src/aeat/application/evidence/test_evidence.py src/aeat/application/inventory/test_inventory.py src/aeat/application/ledger/test_evidence.py src/aeat/application/ledger/test_business_operation_invoice.py src/aeat/application/live/test_verify.py src/aeat/application/live/test_expedientes.py src/aeat/application/live/test_notifications.py src/aeat/application/live/test_censo_snapshot.py src/aeat/application/live/test_borrador_100.py` passed with 145 tests.
- `uv run --no-sync ruff check src/aeat/application/inventory/_service.py src/aeat/application/ledger/_evidence.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/inventory/test_inventory.py src/aeat/application/ledger/test_evidence.py` passed with 31 tests after the wording cleanup.
- `rg -n "storage_path\\(|\\.jsonl|write_text\\(|read_text\\(|aeat_.*dir" src/aeat/application/evidence/_service.py src/aeat/application/inventory/_service.py src/aeat/application/ledger/_evidence.py src/aeat/application/ledger/_business_operation_invoice.py src/aeat/application/live/_verify.py src/aeat/application/live/_expedientes.py src/aeat/application/live/_notifications.py src/aeat/application/live/_snapshot_base.py` returned no hits.

## Notes

`W12.P24.S98` remains separate remote-mirror work. `W12.P24.S99` remains separate retained-file-store test proof for export-only boundaries.
