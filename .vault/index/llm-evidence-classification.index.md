---
generated: true
tags:
  - '#index'
  - '#llm-evidence-classification'
date: '2026-06-10'
related:
  - '[[2026-06-10-llm-evidence-classification-W01-P01-S01]]'
  - '[[2026-06-10-llm-evidence-classification-W01-P01-S02]]'
  - '[[2026-06-10-llm-evidence-classification-W01-P01-S03]]'
  - '[[2026-06-10-llm-evidence-classification-W01-P01-S05]]'
  - '[[2026-06-10-llm-evidence-classification-W01-P02-S04]]'
  - '[[2026-06-10-llm-evidence-classification-W01-P02-S06]]'
  - '[[2026-06-10-llm-evidence-classification-adr]]'
  - '[[2026-06-10-llm-evidence-classification-audit]]'
  - '[[2026-06-10-llm-evidence-classification-plan]]'
  - '[[2026-06-10-llm-evidence-classification-research]]'
---

# `llm-evidence-classification` feature index

Auto-generated index of all documents tagged with `#llm-evidence-classification`.

## Documents

### adr

- `2026-06-10-llm-evidence-classification-adr` - `llm-evidence-classification` adr: `Evidence-aware LLM ledger classification (Stage-3): on-host/local-first reading; cloud only behind a consent gate; splitting in scope` | (**status:** `accepted`)

### audit

- `2026-06-10-llm-evidence-classification-audit` - `llm-evidence-classification` audit: `Wave W01 code review`

### exec

- `2026-06-10-llm-evidence-classification-W01-P01-S01` - Define the unified internal multimodal evidence-input representation (media kind, bytes-or-handle, content hash)
- `2026-06-10-llm-evidence-classification-W01-P01-S02` - Resolve a transaction's purchase_invoice_evidence_id and attachment_ids to evidence bytes read from secure storage into memory only, never a temp file
- `2026-06-10-llm-evidence-classification-W01-P01-S03` - Add a real-behaviour test for evidence resolution from linked ids to decrypted evidence-input
- `2026-06-10-llm-evidence-classification-W01-P01-S05` - Make PurchaseInvoiceEvidence reference an Attachment whose bytes live in the encrypted AttachmentStore, replacing source_path as the byte source with an in-store read
- `2026-06-10-llm-evidence-classification-W01-P02-S04` - Add the cloud-upload consent-gate posture to central Settings (default-off, re-affirmed per invocation, gestor-barred)
- `2026-06-10-llm-evidence-classification-W01-P02-S06` - Test the cloud-consent gate is default-off, re-affirmed per invocation, and refused for a gestor context

### plan

- `2026-06-10-llm-evidence-classification-plan` - `llm-evidence-classification` `Evidence-aware LLM ledger classification (Stage-3)` plan

### research

- `2026-06-10-llm-evidence-classification-research` - `llm-evidence-classification` research: `Evidence-aware LLM ledger classification (Stage-3): feeding attached evidence into the classifier`
