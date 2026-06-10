---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-10'
step_id: 'S05'
related:
  - "[[2026-06-10-llm-evidence-classification-plan]]"
---




# Make PurchaseInvoiceEvidence reference an Attachment whose bytes live in the encrypted AttachmentStore, replacing source_path as the byte source with an in-store read

## Scope

- `src/aeat/application/ledger/_evidence.py`

## Description

- Rework `add()` to copy invoice bytes into the encrypted `AttachmentStore` and record the content-addressed `attachment_id`.
- Add `attachment_id` field to `PurchaseInvoiceEvidence`; demote `source_path` to a provenance breadcrumb (never a byte source).

## Outcome

Commit `983143078`. Existing evidence suite (11 tests) green; no torn-write to the secure-storage invariant.

## Notes

Part of Wave W01; reviewed in audit `2026-06-10-llm-evidence-classification-audit` (gate PASS).
