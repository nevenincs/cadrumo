---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S04'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

# Verify per-dir live-vs-vestigial write status of the var/financial catalogue dirs and record the verdicts

## Scope

- `.vault/audit`

## Description

- Grep every production (non-test) consumer of each `var/financial/*` catalogue settings field plus the two registry store dirs, then read the persistence paths and pinning tests to judge on-disk-write liveness at HEAD.
- Confirm the four financial file-envelope catalogues are live via `default_rotation_plan` / `default_blob_store_roots` in `_rotation.py` (each with a distinct master-key HKDF context), and the registry parity store via the registry CLI default.
- Confirm `cadrumo_purchase_invoice_evidence_dir` and `cadrumo_ledgers_dir` are consumer-less: their data migrated to the encrypted secure-object store, and the secure-storage tests assert the plaintext directories are never written.
- Record the per-dir verdicts and the S02 keep/delete plan in the feature audit document.

## Outcome

Six directories are LIVE and S02 keeps + derives them: `cadrumo_financial_txs_dir`, `cadrumo_invoices_dir`, `cadrumo_attachments_dir`, `cadrumo_usage_ratios_path`, `cadrumo_registry_parity_store_dir`, and `cadrumo_registry_disk_cache_dir` (the last relocated only in the cache-relocation phase). Two directories are VESTIGIAL and S02 deletes them: `cadrumo_purchase_invoice_evidence_dir` and `cadrumo_ledgers_dir`. The verdicts, the evidence per dir, and the full reference-sweep list for the two deletions are recorded in the feature audit document. This unblocks S02.

## Notes

The audit records a residual lifecycle question deferred to a later wave: whether the four live financial file-envelope catalogues still accumulate on-disk envelopes in the common secure-object-only flow, or whether the rotation plan now visits directories that are empty in practice. That is a dead-mechanism / lifecycle question and does not change the S02 keep decision, since those fields are consumed by live production code regardless.
