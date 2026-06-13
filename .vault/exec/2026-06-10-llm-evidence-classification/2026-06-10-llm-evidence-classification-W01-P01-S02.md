---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S02'
related:
  - "[[2026-06-10-llm-evidence-classification-plan]]"
---




# Resolve a transaction's purchase_invoice_evidence_id and attachment_ids to evidence bytes read from secure storage into memory only, never a temp file

## Scope

- `src/aeat/application/ledger/_evidence.py`

## Description

- Add `resolve_attachment_evidence_input` and `resolve_purchase_invoice_evidence_input` that read evidence bytes from the encrypted `AttachmentStore` into memory only.
- Refuse records without an in-store `attachment_id` rather than reading `source_path`.

## Outcome

Commit `983143078`. Real-adapter resolver tests green.

## Notes

Part of Wave W01; reviewed in audit `2026-06-10-llm-evidence-classification-audit` (gate PASS).
