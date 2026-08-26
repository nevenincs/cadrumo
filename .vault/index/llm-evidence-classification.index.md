---
generated: true
tags:
  - '#index'
  - '#llm-evidence-classification'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:c37a5454563c9c3945843cfe651c869e907debe4e1d8d64d264b8ec45b7c46f8'
related:
  - '[[2026-06-10-llm-evidence-classification-adr]]'
  - '[[2026-06-10-llm-evidence-classification-audit]]'
  - '[[2026-06-10-llm-evidence-classification-plan]]'
  - '[[2026-06-10-llm-evidence-classification-research]]'
  - '[[2026-06-11-llm-evidence-classification-audit]]'
  - '[[2026-06-12-llm-evidence-classification-audit]]'
  - '[[2026-06-13-llm-evidence-classification-adr]]'
  - '[[2026-06-13-llm-evidence-classification-audit]]'
  - '[[2026-06-13-llm-evidence-classification-plan]]'
  - '[[2026-06-13-llm-evidence-classification-research]]'
  - '[[2026-06-14-llm-evidence-classification-audit]]'
---

# `llm-evidence-classification` feature index

Auto-generated index of all documents tagged with `#llm-evidence-classification`.

## Documents

### adr

- `2026-06-10-llm-evidence-classification-adr` - `llm-evidence-classification` adr: `Evidence-aware LLM ledger classification (Stage-3): on-host/local-first reading; cloud only behind a consent gate; splitting in scope` | (**status:** `accepted`)
- `2026-06-13-llm-evidence-classification-adr` - `llm-evidence-classification` adr: `Default local vision model bound to consumer-grade hardware` | (**status:** `accepted`)

### audit

- `2026-06-10-llm-evidence-classification-audit` - `llm-evidence-classification` audit: `Wave W01 code review`
- `2026-06-11-llm-evidence-classification-audit` - `llm-evidence-classification` audit: `Persona roll round 1: evidence-aware LLM classification pipeline`
- `2026-06-12-llm-evidence-classification-audit` - `llm-evidence-classification` audit: `Plan closeout: 9 remaining-item disposition`
- `2026-06-13-llm-evidence-classification-audit` - `llm-evidence-classification` audit: `Persona roll round 2: full evidence-aware pipeline against real codex CLI`
- `2026-06-14-llm-evidence-classification-audit` - `llm-evidence-classification` audit: `Live local-vision classification verified end to end (qwen2.5vl)`

### exec

- `2026-06-10-llm-evidence-classification-W01-P01-S01` - Define the unified internal multimodal evidence-input representation (media kind, bytes-or-handle, content hash)
- `2026-06-10-llm-evidence-classification-W01-P01-S02` - Resolve a transaction's purchase_invoice_evidence_id and attachment_ids to evidence bytes read from secure storage into memory only, never a temp file
- `2026-06-10-llm-evidence-classification-W01-P01-S03` - Add a real-behaviour test for evidence resolution from linked ids to decrypted evidence-input
- `2026-06-10-llm-evidence-classification-W01-P01-S05` - Make PurchaseInvoiceEvidence reference an Attachment whose bytes live in the encrypted AttachmentStore, replacing source_path as the byte source with an in-store read
- `2026-06-10-llm-evidence-classification-W01-P02-S04` - Add the cloud-upload consent-gate posture to central Settings (default-off, re-affirmed per invocation, gestor-barred)
- `2026-06-10-llm-evidence-classification-W01-P02-S06` - Test the cloud-consent gate is default-off, re-affirmed per invocation, and refused for a gestor context
- `2026-06-10-llm-evidence-classification-W03-P07-S25` - Add an application path that validates children-sum-to-parent and sign invariants and drives split_transaction from a reviewed suggestion
- `2026-06-10-llm-evidence-classification-W03-P07-S26` - Derive each child's regulated iva_rate, taxable_base, and iva_amount from the registry, never from the model
- `2026-06-10-llm-evidence-classification-W03-P07-S27` - Stamp evidence provenance on each child transaction produced by the split
- `2026-06-10-llm-evidence-classification-W03-P07-S28` - Add a CLI surface for the evidence-driven split suggest and apply flow
- `2026-06-10-llm-evidence-classification-W03-P07-S29` - Add split-invariant, registry-derived-number, and per-child provenance roundtrip tests
- `2026-06-10-llm-evidence-classification-W02-P05-S17` - Extend the LocalAdapter with the Ollama images field and add on-host PDF rasterisation for a local vision model
- `2026-06-10-llm-evidence-classification-W02-P05-S18` - Fold Attachment.sha256 into the LLM cache build_key for multimodal evidence inputs
- `2026-06-10-llm-evidence-classification-W02-P05-S19` - Add a cache-key collision test proving two evidence docs under the same prompt yield distinct keys
- `2026-06-10-llm-evidence-classification-W02-P05-S20` - Add an on-host vision read test (PDF rasterise plus local in-memory images path)
- `2026-06-10-llm-evidence-classification-W03-P08-S32` - Pass the nitpicky Sphinx docs-build gate
- `2026-06-10-llm-evidence-classification-W04-P09-S34` - Persona setup: create a fresh profile, import a real-shaped bank statement, and attach a real purchase-invoice PDF as secure-storage evidence
- `2026-06-10-llm-evidence-classification-W04-P09-S35` - Roll classify --llm with a real cloud CLI (agy/codex) and --read-evidence --evidence-acknowledged
- `2026-06-10-llm-evidence-classification-W04-P09-S36` - Roll classify --llm --saturate against a real cloud CLI
- `2026-06-10-llm-evidence-classification-W04-P09-S37` - Roll split --llm --read-evidence --apply against a real multi-line invoice with a real cloud CLI
- `2026-06-13-llm-evidence-classification-W01-P01-S01` - Thread provider Optional with lazy text-classifier resolution in suggest/saturate/split classification
- `2026-06-13-llm-evidence-classification-W01-P01-S02` - Route --read-evidence into the LLM path when --llm is absent
- `2026-06-13-llm-evidence-classification-W01-P01-S03` - Test image evidence without --llm classifies via the vision model and text/no-evidence without --llm refuses instructively
- `2026-06-13-llm-evidence-classification-W02-P02-S04` - Source licence-clean text-layer PDF, scanned/image PDF, and image invoices into a fixtures corpus
- `2026-06-13-llm-evidence-classification-W02-P02-S05` - Write a provenance sidecar per corpus fixture declaring real_corpus or synthetic_generated and its source
- `2026-06-13-llm-evidence-classification-W02-P02-S06` - Generate adversarial fixture variants (prompt-injection invoice, malformed/empty PDF, multi-page, foreign-language)
- `2026-06-13-llm-evidence-classification-W03-P03-S07` - Adversarially test evidence parsing (text-layer, in-memory rasterise, vision dispatch) against the corpus
- `2026-06-13-llm-evidence-classification-W03-P03-S08` - Adversarially test parse_response: prompt-injection JSON, hostile/oversized output, out-of-allow-list values are rejected

### plan

- `2026-06-10-llm-evidence-classification-plan` - `llm-evidence-classification` `Evidence-aware LLM ledger classification (Stage-3)` plan
- `2026-06-13-llm-evidence-classification-plan` - `llm-evidence-classification` `Evidence corpus and adversarial hardening` plan

### research

- `2026-06-10-llm-evidence-classification-research` - `llm-evidence-classification` research: `Evidence-aware LLM ledger classification (Stage-3): feeding attached evidence into the classifier`
- `2026-06-13-llm-evidence-classification-research` - `llm-evidence-classification` research: `Local vision model for consumer-grade on-host evidence reading`
