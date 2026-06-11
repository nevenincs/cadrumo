---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-10'
step_id: 'S27'
related:
  - "[[2026-06-10-llm-evidence-classification-plan]]"
---




# Stamp evidence provenance on each child transaction produced by the split

## Scope

- `src/aeat/application/ledger/_llm_classification.py`

## Description

- In `apply_evidence_split`, link the parent invoice's evidence (`purchase_invoice_evidence_id`, else `attachment_ids`) onto every child via the per-child `update_manual_transaction_fields` patch, and stamp `classified_by` with the proposer's `llm:<model>` provenance through `classified_by_override`.

## Outcome

Commit `a9b654ed9`. Test seeds a real RECEIVED invoice, links it to the parent, splits, and asserts each persisted child carries the same `purchase_invoice_evidence_id`; the per-child manual write re-verifies the reference exists in the invoice catalogue.

## Notes

The plan anchored S27 at `_actions_split_merge.py`; the durable home is instead the composition service `apply_evidence_split`, so the general manual `split_transaction` stays evidence-neutral (children default NOT_YET_PROCESSED) and only the evidence-driven path links evidence — honouring `composition-service-no-parallel-write-path`.
