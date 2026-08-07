---
generated: true
tags:
  - '#index'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:cb632c14d5d787334aeea71471edb93d7a0d15ca9a0ea1e66afb11668f968257'
related:
  - '[[2026-08-07-unstructured-document-ingestion-W02-P04-S11]]'
  - '[[2026-08-07-unstructured-document-ingestion-W03-P08-S25]]'
  - '[[2026-08-07-unstructured-document-ingestion-W03-P08-S27]]'
  - '[[2026-08-07-unstructured-document-ingestion-W03-P08-S29]]'
  - '[[2026-08-07-unstructured-document-ingestion-adr]]'
  - '[[2026-08-07-unstructured-document-ingestion-confirm-boundary-under-declaration-audit]]'
  - '[[2026-08-07-unstructured-document-ingestion-operations-adr]]'
  - '[[2026-08-07-unstructured-document-ingestion-plan]]'
  - '[[2026-08-07-unstructured-document-ingestion-provisioning-adr]]'
---

# `unstructured-document-ingestion` feature index

Auto-generated index of all documents tagged with `#unstructured-document-ingestion`.

## Documents

### adr

- `2026-08-07-unstructured-document-ingestion-adr` - `unstructured-document-ingestion` adr: `Unstructured document ingestion: a transcription-anchored semantic pipeline` | (**status:** `proposed`)
- `2026-08-07-unstructured-document-ingestion-operations-adr` - `unstructured-document-ingestion` adr: `Operational surface: batch ingestion, the human review process, the consent lifecycle, and deinstallation` | (**status:** `proposed`)
- `2026-08-07-unstructured-document-ingestion-provisioning-adr` - `unstructured-document-ingestion` adr: `Model provisioning, adaptive selection, and the cadrumo[llm] distribution boundary` | (**status:** `proposed`)

### audit

- `2026-08-07-unstructured-document-ingestion-confirm-boundary-under-declaration-audit` - `unstructured-document-ingestion` audit: `Confirm-boundary under-declaration sweep`

### exec

- `2026-08-07-unstructured-document-ingestion-W02-P04-S11` - Produce the deterministic text-layer transcription into DocumentTranscription with reading order and printed forms preserved, gated by fixture tests asserting byte-faithful printed forms
- `2026-08-07-unstructured-document-ingestion-W03-P08-S25` - Normalize tabular dialects covering delimiter, decimal convention, encoding, preamble rows, summary rows and embedded newlines into one typed table, gated by all nine bundled operator CSV exports normalizing against the current 1-of-7 baseline
- `2026-08-07-unstructured-document-ingestion-W03-P08-S27` - Project rows deterministically under a confirmed mapping so the model never touches a cell value, gated by a property test asserting projected values byte-equal their source cells
- `2026-08-07-unstructured-document-ingestion-W03-P08-S29` - Enrol the mapping lane as statement-import fallback strictly after the exact fixed-layout providers, gated by a known-bank fixture still taking the exact provider and an unknown-format fixture reaching the mapping lane

### plan

- `2026-08-07-unstructured-document-ingestion-plan` - `unstructured-document-ingestion` plan
