---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:fa13e7fd73067d092973cd6cd017401bd71e1a443174f94eae81d713910a1913'
step_id: 'S07'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Widen InvoiceDraft with a direction suggestion, retencion rate and amount, suplidos, discrepancy findings, and the transcription content address, gated by model and roundtrip tests. The counterparty rename clause is struck: the ADR specifying it is proposed rather than accepted, so there is no landed rename to verify, and the vocabulary reconciliation is tracked separately

## Scope

- `src/cadrumo/application/ledger/_evidence_draft.py`

## Description

## Outcome

Executed. Verified against HEAD: the draft carries `retencion_rate`, `retencion_amount`, `suplidos_amount` and `discrepancies`, and the direction answer is stamped as a SUGGESTION. The row's "transcription content address" ships as an evidence content hash rather than under that name.

**Retrospectively reconstructed on 2026-08-13 at operator direction. NOT a contemporaneous account** — nobody observed this work being done. What is recorded is that the deliverable exists at HEAD and how that was established. Per-row verification detail is in the record-gap close audit.

## Notes
