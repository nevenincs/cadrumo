---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:1003a48046d5b83015a84259231bb4b947fe739f6a961370093a65b7ff20eafa'
step_id: 'S01'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

# Make generic manual-field updates refuse all evidence fields, reserve evidence catalogue and provenance mutation for attach, and expose a single atomic invoice-only linkage writer

## Scope

- `src/cadrumo/application/ledger/_actions_manual.py`

## Description

- Add module constant `_EVIDENCE_PATCH_FIELDS` naming `purchase_invoice_evidence_id` and `attachment_ids` as the reserved evidence axis.
- Add a private `_evidence_authority` keyword to `update_manual_transaction_fields` and `update_manual_transaction`; the patch door refuses when it sets an evidence field and the command door refuses when the replacement changes evidence, both directing the caller to `aeat app ledger attach`.
- Thread `_evidence_authority=True` from `attach_manual_transaction_evidence` (the sole evidence writer) through the delegation so attach still writes evidence.
- Add `link_manual_transaction_invoice`, a single atomic invoice-only linkage writer that resolves the transaction, enforces the invoice missing and cross-bucket policy before any catalogue write, then delegates the bidirectional link/persist to the invoices facade; it never touches evidence. Export it from the ledger package facade.
- Sweep the forced consumer changes: the CLI `ledger link --evidence-id` branch routes through attach; the LLM no-split classifier drops the redundant evidence patch (parent carry-forward preserves it); the LLM split-child evidence inheritance threads `_evidence_authority=True` (relocated to the atomic writer in P02).

## Outcome

- Evidence catalogue and provenance mutation is now reachable only through the attach authority; the generic patch and command doors refuse it.
- `link_manual_transaction_invoice` exposes the invoice-only writer P03 will route the CLI `ledger link` through.
- Files: `_actions_manual.py`, `__init__.py`, `_llm_classification.py`, `entrypoints/cli/_ledger.py`, plus consumer-sweep test updates in `test_actions_update_evidence.py` and `test_attach_purchase_evidence_store.py`.
- Verification: ledger application suite 375 passed; CLI link/check, ledger-modelo-staleness, catalogue-invoice-link, LLM evidence-split, and evidence-draft suites green; ruff clean; `--collect-only` clean. Commit `744c61adb8`.

## Notes

- The split-child evidence inheritance passing `_evidence_authority=True` through the generic door is an interim: P02.S04 moves that inheritance into the atomic split writer in `_actions_split_manual.py`, at which point the split path no longer touches the generic door.
- Comprehensive bypass-impossible and atomicity proofs (invoice linkage cannot mutate evidence; failed attach/link leaves catalogue, provenance, and event history unchanged) are S02/S03; S01 landed a baseline proof so the suite stays green.
