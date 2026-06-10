---
tags:
  - '#plan'
  - '#llm-evidence-classification'
date: '2026-06-10'
tier: L3
related:
  - '[[2026-06-10-llm-evidence-classification-adr]]'
  - '[[2026-06-10-llm-evidence-classification-research]]'
  - '[[2026-06-04-llm-ledger-classification-adr]]'
---


# `llm-evidence-classification` `Evidence-aware LLM ledger classification (Stage-3)` plan

## Wave `W01` - Foundation - evidence resolution, decrypted-temp-file lifecycle, privacy boundary

Resolve a transaction's linked evidence to decrypted bytes plus media kind through the existing secure-object path, define the unified internal multimodal evidence-input representation, and establish the privacy boundary: a permitted-provider Settings surface and a bounded decrypted-temp-file lifecycle. Backs every later Wave; both downstream Waves consume the evidence-input representation and the privacy gate. Authorised by the Stage-3 ADR and research.

### Phase `W01.P01` - Evidence resolution and internal representation

Define the unified internal multimodal evidence-input representation and resolve a transaction's linked evidence to decrypted bytes plus media kind.

- [ ] `W01.P01.S01` - Define the unified internal multimodal evidence-input representation (media kind, bytes-or-handle, content hash); `src/aeat/application/ledger/_evidence_input.py`.
- [ ] `W01.P01.S02` - Resolve a transaction's purchase_invoice_evidence_id and attachment_ids to decrypted bytes plus media kind via the secure-object path; `src/aeat/application/ledger/_evidence.py`.
- [ ] `W01.P01.S03` - Add a real-behaviour test for evidence resolution from linked ids to decrypted evidence-input; `src/aeat/application/ledger/tests/test_evidence_input.py`.

### Phase `W01.P02` - Privacy boundary and temp-file lifecycle

Add the permitted-provider Settings surface and a bounded decrypted-temp-file lifecycle for the CLI-agent route.

- [ ] `W01.P02.S04` - Add the permitted-evidence-provider posture and unredacted-path policy fields to central Settings; `src/aeat/core/config.py`.
- [ ] `W01.P02.S05` - Add a bounded decrypted-temp-file lifecycle helper (private location, prompt removal, never logged); `src/aeat/application/ledger/_evidence_tempfile.py`.
- [ ] `W01.P02.S06` - Test the temp-file lifecycle and that the permitted-provider gate refuses a disallowed provider; `src/aeat/application/ledger/tests/test_evidence_tempfile.py`.

## Wave `W02` - Reading-for-selection (Stage-3a) - CLI-agent transport, prompt extension, advisory, provenance, cache

Build the decrypted-file-path transport for the claude/agy/codex subprocess agents (the production classify surface today), extend the classify and saturate prompts to read the attached document and select spending category plus IVA category guarded by the allow-list, add the printed-vs-derived IVA advisory cross-check, stamp llm-model plus cited-evidence provenance, surface low-confidence reads, retain the pdfplumber text-layer fast-path and LOCAL-only route, and fold the evidence content address into the LLM cache key. Depends on W01; W03 reuses the transport and prompt plumbing.

### Phase `W02.P03` - CLI-agent transport and prompt extension

Inject the decrypted evidence file path into the classify and saturate prompts via the subprocess classifier and gate it on the permitted-provider posture.

- [ ] `W02.P03.S07` - Extend PromptSpec.render to inject an attached-evidence file path and an instruction to read it; `src/aeat/domain/transactions/_llm.py`.
- [ ] `W02.P03.S08` - Thread the resolved evidence temp-file path through SubprocessLLMClassifier.classify into the prompt; `src/aeat/domain/transactions/_llm.py`.
- [ ] `W02.P03.S09` - Wire opt-in permitted-provider-gated evidence resolution into suggest_llm_classification and saturate_llm_classification; `src/aeat/application/ledger/_llm_classification.py`.
- [ ] `W02.P03.S10` - Add a --read-evidence opt-in flag to the classify --llm CLI handlers; `src/aeat/entrypoints/cli/_ledger.py`.
- [ ] `W02.P03.S11` - Test that the evidence path reaches the rendered prompt and that the provider gate is enforced; `src/aeat/domain/transactions/tests/test_llm_evidence_prompt.py`.

### Phase `W02.P04` - Selection grounding, advisory cross-check, provenance

Guard evidence-read category and IVA-category selection with the allow-list, add the printed-vs-derived IVA advisory, stamp provenance, and surface low-confidence reads.

- [ ] `W02.P04.S12` - Keep the parse_response allow-list guard over evidence-read category and iva_category selection; `src/aeat/domain/transactions/_llm.py`.
- [ ] `W02.P04.S13` - Add a printed-vs-derived IVA advisory cross-check as a non-blocking source diagnostic; `src/aeat/application/ledger/_llm_classification.py`.
- [ ] `W02.P04.S14` - Stamp classified_by llm-model and the cited evidence_id and attachment_id into classification and evidence provenance on apply; `src/aeat/application/ledger/_llm_classification.py`.
- [ ] `W02.P04.S15` - Surface a low-confidence or refused evidence read to the operator rather than persisting silently; `src/aeat/application/ledger/_llm_classification.py`.
- [ ] `W02.P04.S16` - Add allow-list guard, advisory cross-check, and provenance-stamping tests; `src/aeat/application/ledger/tests/test_llm_evidence_selection.py`.

### Phase `W02.P05` - Text-layer fast-path and cache key

Add the pdfplumber text-layer fast-path and LOCAL-only route, and fold the evidence content address into the LLM cache key.

- [ ] `W02.P05.S17` - Add a pdfplumber text-layer fast-path for clean text-native PDFs and as the LOCAL-only route feeding the text prompt; `src/aeat/application/ledger/_evidence_textlayer.py`.
- [ ] `W02.P05.S18` - Fold Attachment.sha256 into the LLM cache build_key for multimodal evidence inputs; `src/aeat/adapters/outbound/llm/_cache.py`.
- [ ] `W02.P05.S19` - Add a cache-key collision test proving two evidence docs under the same prompt yield distinct keys; `src/aeat/adapters/outbound/llm/tests/test_cache.py`.
- [ ] `W02.P05.S20` - Add a text-layer extraction test on a clean text-native fixture PDF; `src/aeat/application/ledger/tests/test_evidence_textlayer.py`.

## Wave `W03` - Splitting (Stage-3b) - evidence-driven N-way split suggestion and application

Add the N-way split response schema and split-proposal prompt, parse and validate the proposal under the allow-list, and drive split_transaction from a reviewed suggestion with children-sum-to-parent and sign invariants, registry-derived child numbers, and per-child evidence provenance. Depends on W01 and W02.

### Phase `W03.P06` - Split suggestion schema and prompt

Define the N-way split response schema and split-proposal prompt and parse/validate the proposal under the allow-list.

- [ ] `W03.P06.S21` - Define the N-way split response schema (children each carrying amount, category, iva_category, evidence citation); `src/aeat/domain/transactions/_llm.py`.
- [ ] `W03.P06.S22` - Add a split-proposal prompt spec instructing the model to read the invoice and propose children; `src/aeat/domain/transactions/_llm.py`.
- [ ] `W03.P06.S23` - Parse and validate the split response under the allow-list guard; `src/aeat/domain/transactions/_llm.py`.
- [ ] `W03.P06.S24` - Add split-schema and parse-validation tests; `src/aeat/domain/transactions/tests/test_llm_split_schema.py`.

### Phase `W03.P07` - Split application path, CLI, provenance

Validate split invariants and drive split_transaction from a reviewed suggestion with registry-derived child numbers and per-child evidence provenance.

- [ ] `W03.P07.S25` - Add an application path that validates children-sum-to-parent and sign invariants and drives split_transaction from a reviewed suggestion; `src/aeat/application/ledger/_llm_classification.py`.
- [ ] `W03.P07.S26` - Derive each child's regulated iva_rate, taxable_base, and iva_amount from the registry, never from the model; `src/aeat/application/ledger/_llm_classification.py`.
- [ ] `W03.P07.S27` - Stamp evidence provenance on each child transaction produced by the split; `src/aeat/application/ledger/_actions_split_merge.py`.
- [ ] `W03.P07.S28` - Add a CLI surface for the evidence-driven split suggest and apply flow; `src/aeat/entrypoints/cli/_ledger.py`.
- [ ] `W03.P07.S29` - Add split-invariant, registry-derived-number, and per-child provenance roundtrip tests; `src/aeat/application/ledger/tests/test_llm_evidence_split.py`.

### Phase `W03.P08` - Documentation and conformance gates

Update the classify how-to for the evidence-reading and split flow and pass the command-conformance and docs-build gates.

- [ ] `W03.P08.S30` - Update the classify how-to with the evidence-reading and evidence-driven split flow; `docs/how-to/classify-with-llm.md`.
- [ ] `W03.P08.S31` - Pass the documented-command-conformance gate for the new evidence and split flags; `src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py`.
- [ ] `W03.P08.S32` - Pass the nitpicky Sphinx docs-build gate; `dev/docs/tests/test_docs_build.py`.

## Description

Stage-3 of LLM ledger classification: feed a transaction's attached evidence
(purchase-invoice PDF, receipt image, email, Drive/URL document) into the existing
classify/saturate pipeline so the model reads the document to select the spending
category and IVA category and to propose an N-way split of one transaction into
several children. Authorised by the Stage-3 ADR and its research, building on the
landed Stage-1 (suggest/apply/reject) and Stage-2 (saturate: select IVA category,
derive rate/base/amount). The operator-approved build order is realised in the Wave
order: W01 establishes evidence resolution and the privacy boundary; W02 delivers
reading-for-selection over the CLI-agent file-path transport (the production
classify surface today is the subprocess `claude`/`agy`/`codex` agents) with the
text-layer fast-path and cache-key fix; W03 adds evidence-driven N-way splitting.
Wiring the HTTP-SDK multimodal transports (Anthropic document block, Gemini
inline/File-API, OpenAI input_file) into the classify path is net-new and is
deliberately out of scope for this plan, deferred to a follow-up; the W02 transport
abstraction is built so adding it later is additive.

Every Step preserves the hard constraints from the ADR: the LLM selects
category/iva_category from the registry-grounded allow-list and proposes split
boundaries, but never emits the persisted `iva_rate`/`taxable_base`/`iva_amount`
(registry-derived; an invoice-printed figure is an advisory cross-check only); the
suggest-review-apply/reject contract and human-in-the-loop precision safeguard
hold; a low-confidence or refused read surfaces to the operator rather than
persisting silently; and decrypted FINANCIAL-sensitivity evidence leaves the
process only along an explicitly permitted path with a bounded temp-file lifecycle.

## Steps







## Parallelization

Waves are sequenced: W01 must land before W02 (W02 consumes the evidence-input
representation and the privacy gate), and W02 before W03 (W03 reuses the transport,
prompt plumbing, and provenance stamping). Within W01, `W01.P01` and `W01.P02` are
largely independent and may proceed in parallel. Within W02, `W02.P03` (transport
plus prompt injection) is the prerequisite; once it lands, `W02.P04` (selection
grounding, advisory, provenance) and `W02.P05` (text-layer fast-path, cache key)
carry no hard interdependency and may parallelise. Within W03, `W03.P06` (schema
plus prompt plus parse) precedes `W03.P07` (application path plus CLI plus
provenance); `W03.P08` (docs plus conformance gates) runs after `W03.P07` lands the
new CLI flags. Within any Phase, each implementation Step precedes its paired test
Step.

## Verification

The plan is complete when every Step in every Wave is closed (`- [x]`) and each
criterion below verifies:

- Evidence resolution returns decrypted bytes plus media kind from a transaction's
  linked ids, proven by a real-behaviour test against the secure-object path
  (`W01.P01.S03`).
- The permitted-provider gate refuses a disallowed provider and the decrypted
  temp-file is created in a private location, removed after use, and never logged
  (`W01.P02.S06`).
- The resolved evidence path reaches the rendered classify/saturate prompt and the
  provider gate is enforced (`W02.P03.S11`).
- The `parse_response` allow-list guard rejects out-of-allow-list category or
  iva_category from an evidence read; the printed-vs-derived IVA advisory fires on
  mismatch; applied classifications stamp `llm:<model>` plus the cited evidence id
  (`W02.P04.S16`).
- Two distinct evidence documents under the same prompt text yield distinct LLM
  cache keys; the text-layer fast-path extracts a clean text-native PDF
  (`W02.P05.S19`, `W02.P05.S20`).
- The split application path enforces children-sum-to-parent and sign invariants,
  each child's regulated numbers are registry-derived (never model-emitted), and
  per-child evidence provenance survives a strict save/load roundtrip
  (`W03.P07.S29`).
- The documented-command-conformance gate passes for the new evidence and split
  flags, and the nitpicky docs-build gate passes (`W03.P08.S31`, `W03.P08.S32`).
- Across the suite, no test uses mocks, skips, xfail, or tautological assertions,
  and no path lets the LLM emit a persisted regulated tax number.
