---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S96'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-w12-p24-s96-side-store-classification-exec]]'
---

# `secure-storage-production-hardening` `W12.P24.S96` Side-Store Classification

## Description

- Classified the scoped application file-store surfaces named by `W12.P24.S96`.
- Reconciled current code against the W05.P09.S36 side-store inventory, S37-S40 migration reviews, the S40 export-only ADR, and W17 ledger JSONL follow-up rows.
- Recorded that evidence bundle manifests, inventory ledgers, live verification observations, live expedientes snapshots, live notifications snapshots, and shared live snapshots are already secure-object backed.
- Recorded that evidence bundle ZIP export is the retained export-only boundary.
- Preserved purchase invoice evidence JSONL and business-operation invoice JSONL as pending secure-object migrations under `W17.P37.S424` and `W17.P37.S425`.

## Changed Surface

- `.vault/audit/2026-06-02-secure-storage-production-hardening-W12-P24-S96-side-store-classification.md`

## Outcome

Closed for S96 classification.

No code was changed. The classification does not accept any sensitive default bucket-local JSON or JSONL store as plaintext. The two remaining ledger JSONL stores are explicitly tracked as pending migration rather than folded into the S40 export exception.

## Verification

- Reviewed `src/aeat/application/evidence/_service.py`, `src/aeat/application/inventory/_service.py`, `src/aeat/application/ledger/_evidence.py`, `src/aeat/application/ledger/_business_operation_invoice.py`, `src/aeat/application/live/_verify.py`, `src/aeat/application/live/_expedientes.py`, `src/aeat/application/live/_notifications.py`, and `src/aeat/application/live/_snapshot_base.py`.
- Reviewed `.vault/audit/2026-05-28-secure-storage-production-hardening-W05-P09-S36-side-store-inventory.md`, S37-S40 reviews, and `.vault/adr/2026-05-28-secure-storage-production-hardening-W05-P09-S40-adr.md`.
- Confirmed plan rows `W17.P37.S424` and `W17.P37.S425` remain open migration owners.

## Notes

`W12.P24.S97` should use this audit as its input: migrated surfaces can be treated as already resolved, while the two ledger JSONL stores remain implementation work unless explicit ADR-backed exception coverage is created.
