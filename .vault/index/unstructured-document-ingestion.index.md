---
generated: true
tags:
  - '#index'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:f2316f5c576072eacfb62e1096725053217782d62a4df5a94b31289e594b654c'
related:
  - '[[2026-08-07-unstructured-document-ingestion-W01-P01-S01]]'
  - '[[2026-08-07-unstructured-document-ingestion-W01-P01-S02]]'
  - '[[2026-08-07-unstructured-document-ingestion-W01-P01-S03]]'
  - '[[2026-08-07-unstructured-document-ingestion-W01-P02-S04]]'
  - '[[2026-08-07-unstructured-document-ingestion-W01-P02-S05]]'
  - '[[2026-08-07-unstructured-document-ingestion-W02-P04-S11]]'
  - '[[2026-08-07-unstructured-document-ingestion-W03-P08-S25]]'
  - '[[2026-08-07-unstructured-document-ingestion-W03-P08-S27]]'
  - '[[2026-08-07-unstructured-document-ingestion-W03-P08-S29]]'
  - '[[2026-08-07-unstructured-document-ingestion-W04-P09-S31]]'
  - '[[2026-08-07-unstructured-document-ingestion-W06-P12-S45]]'
  - '[[2026-08-07-unstructured-document-ingestion-W06-P12-S59]]'
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

- `2026-08-07-unstructured-document-ingestion-W01-P01-S01` - Add the FieldOrigin provenance StrEnum (EXACT_STRUCTURED, TEXT_LAYER, VISION, TABULAR_MAPPED, OPERATOR) with facade export, gated by enum round-trip tests and the import-hygiene gate
- `2026-08-07-unstructured-document-ingestion-W01-P01-S02` - Add the closed FieldRole StrEnum for tabular column mapping including UNMAPPED, with facade export, gated by a test asserting every importer-consumed role is a member
- `2026-08-07-unstructured-document-ingestion-W01-P01-S03` - Promote EvidenceInput to the application.ledger public facade as a precondition of any consuming change
- `2026-08-07-unstructured-document-ingestion-W01-P02-S04` - Add the single typed DocumentTranscription record (reading-order text with printed forms preserved, page count, source content address, origin with model identity and revision) carrying the EvidenceInput serialization tripwires, gated by a strict roundtrip and tripwire refusal tests
- `2026-08-07-unstructured-document-ingestion-W01-P02-S05` - Wire the encrypted transcription cache through core secure storage keyed by source content address plus transcriber identity, gated by a real-adapter roundtrip, an on-disk mutation anti-tautology proof, and the sensitive-persistence gate scan reaching the new module
- `2026-08-07-unstructured-document-ingestion-W02-P04-S11` - Produce the deterministic text-layer transcription into DocumentTranscription with reading order and printed forms preserved, gated by fixture tests asserting byte-faithful printed forms
- `2026-08-07-unstructured-document-ingestion-W03-P08-S25` - Normalize tabular dialects covering delimiter, decimal convention, encoding, preamble rows, summary rows and embedded newlines into one typed table, gated by all nine bundled operator CSV exports normalizing against the current 1-of-7 baseline
- `2026-08-07-unstructured-document-ingestion-W03-P08-S27` - Project rows deterministically under a confirmed mapping so the model never touches a cell value, gated by a property test asserting projected values byte-equal their source cells
- `2026-08-07-unstructured-document-ingestion-W03-P08-S29` - Enrol the mapping lane as statement-import fallback strictly after the exact fixed-layout providers, gated by a known-bank fixture still taking the exact provider and an unknown-format fixture reaching the mapping lane
- `2026-08-07-unstructured-document-ingestion-W04-P09-S31` - Bundle the licence-clean fixture subset with provenance sidecars, including both COM-2026-0005 entries
- `2026-08-07-unstructured-document-ingestion-W06-P12-S45` - Add the HardwareProfile probe carrying free system memory, accelerator presence, and NVML-backed total and free VRAM, with unknown reported as unverified on diagnostic rows, gated by injected-measurement tests covering every branch
- `2026-08-07-unstructured-document-ingestion-W06-P12-S59` - Distinguish runtime residents from peer-process device usage in the contention snapshot and add the explicit unload action for Cadrumo-selected models, with the refusal naming which remediation applies, gated by injected readings covering both causes and an unload-path test, never touching another process

### plan

- `2026-08-07-unstructured-document-ingestion-plan` - `unstructured-document-ingestion` plan
