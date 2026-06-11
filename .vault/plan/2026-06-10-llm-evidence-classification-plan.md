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

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

<!-- RETIRED: W05 -->

# `llm-evidence-classification` `Evidence-aware LLM ledger classification (Stage-3)` plan

## Wave `W01` - Foundation - secure-storage evidence byte read and cloud-consent posture

Read a transaction's linked evidence bytes from secure storage into memory only (never a temp file), define the unified internal evidence-input representation, and add the default-off, gestor-barred cloud-upload consent posture to central Settings. Backs every later Wave. Authorised by the Stage-3 ADR and research.

### Phase `W01.P01` - Secure-storage evidence byte home, representation, and resolver

Define the in-memory evidence-input representation, make purchase-invoice evidence reference an Attachment so its bytes live in the encrypted AttachmentStore, and resolve a transaction's linked evidence to in-memory bytes read from secure storage (never a temp file).

- [x] `W01.P01.S01` - Define the unified internal multimodal evidence-input representation (media kind, bytes-or-handle, content hash); `src/aeat/application/ledger/_evidence_input.py`.
- [x] `W01.P01.S05` - Make PurchaseInvoiceEvidence reference an Attachment whose bytes live in the encrypted AttachmentStore, replacing source_path as the byte source with an in-store read; `src/aeat/application/ledger/_evidence.py`.
- [x] `W01.P01.S02` - Resolve a transaction's purchase_invoice_evidence_id and attachment_ids to evidence bytes read from secure storage into memory only, never a temp file; `src/aeat/application/ledger/_evidence.py`.
- [x] `W01.P01.S03` - Add a real-behaviour test for evidence resolution from linked ids to decrypted evidence-input; `src/aeat/application/ledger/tests/test_evidence_input.py`.

### Phase `W01.P02` - Cloud-upload consent posture

Add the default-off, per-invocation, gestor-barred cloud-upload consent posture to central Settings and prove it is refused without acknowledgement.

- [x] `W01.P02.S04` - Add the cloud-upload consent-gate posture to central Settings (default-off, re-affirmed per invocation, gestor-barred); `src/aeat/core/config.py`.
- [x] `W01.P02.S06` - Test the cloud-consent gate is default-off, re-affirmed per invocation, and refused for a gestor context; `src/aeat/application/ledger/tests/test_evidence_consent.py`.

## Wave `W02` - Reading-for-selection (Stage-3a) - on-host text-layer and local vision reading, advisory, provenance, cache

Deliver the on-host readers: the in-tree pdfplumber text-layer over in-memory bytes feeding the classify and saturate prompts, and the LocalAdapter extended with the Ollama images field plus on-host PDF rasterisation for a local vision model. Add the allow-list-guarded category/IVA selection, the printed-vs-derived IVA advisory, llm-model plus cited-evidence provenance, low-confidence surfacing, the cloud-consent gate enforcement, and the evidence-content-address cache key. Depends on W01; W03 reuses the reader and prompt plumbing.

### Phase `W02.P03` - On-host text-layer reading and prompt extension

Read evidence bytes from secure storage in-memory, run the in-tree pdfplumber text-layer over them on-host, and inject the extracted text into the classify and saturate prompts. No file is written; nothing leaves the host.

- [x] `W02.P03.S07` - Extend PromptSpec.render to inject extracted evidence text and a read instruction into the classify prompt; `src/aeat/domain/transactions/_llm.py`.
- [x] `W02.P03.S08` - Run the in-tree pdfplumber text-layer over in-memory evidence bytes to produce the prompt text fed to the classifier; `src/aeat/application/ledger/_evidence_textlayer.py`.
- [x] `W02.P03.S09` - Wire opt-in permitted-provider-gated evidence resolution into suggest_llm_classification and saturate_llm_classification; `src/aeat/application/ledger/_llm_classification.py`.
- [x] `W02.P03.S10` - Add a --read-evidence opt-in flag to the classify --llm CLI handlers; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W02.P03.S11` - Test that extracted evidence text reaches the rendered prompt and that no evidence file is written outside secure storage; `src/aeat/domain/transactions/tests/test_llm_evidence_prompt.py`.

### Phase `W02.P04` - Selection grounding, advisory cross-check, provenance

Guard evidence-read category and IVA-category selection with the allow-list, add the printed-vs-derived IVA advisory, stamp provenance, and surface low-confidence reads.

- [x] `W02.P04.S12` - Keep the parse_response allow-list guard over evidence-read category and iva_category selection; `src/aeat/domain/transactions/_llm.py`.
- [x] `W02.P04.S13` - Add a printed-vs-derived IVA advisory cross-check as a non-blocking source diagnostic; `src/aeat/application/ledger/_llm_classification.py`.
- [x] `W02.P04.S14` - Stamp classified_by llm-model and the cited evidence_id and attachment_id into classification and evidence provenance on apply; `src/aeat/application/ledger/_llm_classification.py`.
- [x] `W02.P04.S15` - Surface a low-confidence or refused evidence read to the operator rather than persisting silently; `src/aeat/application/ledger/_llm_classification.py`.
- [x] `W02.P04.S16` - Add allow-list guard, advisory cross-check, and provenance-stamping tests; `src/aeat/application/ledger/tests/test_llm_evidence_selection.py`.
- [x] `W02.P04.S33` - Enforce the cloud-upload consent gate in the evidence-read path: refuse a cloud transport without per-invocation acknowledgement, exclude the file-writing CLI-agent route, and record the consent in provenance; `src/aeat/application/ledger/_llm_classification.py`.

### Phase `W02.P05` - On-host vision reading and cache key

Extend the LocalAdapter with the Ollama images field and on-host PDF rasterisation so a local vision model reads scanned and image evidence in-memory, and fold the evidence content address into the LLM cache key.

- [ ] `W02.P05.S17` - Extend the LocalAdapter with the Ollama images field and add on-host PDF rasterisation for a local vision model; `src/aeat/adapters/outbound/llm/_providers/local.py`.
- [ ] `W02.P05.S18` - Fold Attachment.sha256 into the LLM cache build_key for multimodal evidence inputs; `src/aeat/adapters/outbound/llm/_cache.py`.
- [ ] `W02.P05.S19` - Add a cache-key collision test proving two evidence docs under the same prompt yield distinct keys; `src/aeat/adapters/outbound/llm/tests/test_cache.py`.
- [ ] `W02.P05.S20` - Add an on-host vision read test (PDF rasterise plus local in-memory images path); `src/aeat/adapters/outbound/llm/tests/test_local_vision.py`.

## Wave `W03` - Splitting (Stage-3b) - evidence-driven N-way split suggestion and application

Add the N-way split response schema and split-proposal prompt, parse and validate the proposal under the allow-list, and drive split_transaction from a reviewed suggestion with children-sum-to-parent and sign invariants, registry-derived child numbers, and per-child evidence provenance. Depends on W01 and W02.

### Phase `W03.P06` - Split suggestion schema and prompt

Define the N-way split response schema and split-proposal prompt and parse/validate the proposal under the allow-list.

- [x] `W03.P06.S21` - Define the N-way split response schema (children each carrying amount, category, iva_category, evidence citation); `src/aeat/domain/transactions/_llm.py`.
- [x] `W03.P06.S22` - Add a split-proposal prompt spec instructing the model to read the invoice and propose children; `src/aeat/domain/transactions/_llm.py`.
- [x] `W03.P06.S23` - Parse and validate the split response under the allow-list guard; `src/aeat/domain/transactions/_llm.py`.
- [x] `W03.P06.S24` - Add split-schema and parse-validation tests; `src/aeat/domain/transactions/tests/test_llm_split_schema.py`.

### Phase `W03.P07` - Split application path, CLI, provenance

Validate split invariants and drive split_transaction from a reviewed suggestion with registry-derived child numbers and per-child evidence provenance.

- [x] `W03.P07.S25` - Add an application path that validates children-sum-to-parent and sign invariants and drives split_transaction from a reviewed suggestion; `src/aeat/application/ledger/_llm_classification.py`.
- [x] `W03.P07.S26` - Derive each child's regulated iva_rate, taxable_base, and iva_amount from the registry, never from the model; `src/aeat/application/ledger/_llm_classification.py`.
- [x] `W03.P07.S27` - Stamp evidence provenance on each child transaction produced by the split; `src/aeat/application/ledger/_actions_split_merge.py`.
- [x] `W03.P07.S28` - Add a CLI surface for the evidence-driven split suggest and apply flow; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W03.P07.S29` - Add split-invariant, registry-derived-number, and per-child provenance roundtrip tests; `src/aeat/application/ledger/tests/test_llm_evidence_split.py`.

### Phase `W03.P08` - Documentation and conformance gates

Update the classify how-to for the evidence-reading and split flow and pass the command-conformance and docs-build gates.

- [x] `W03.P08.S30` - Update the classify how-to with the evidence-reading and evidence-driven split flow; `docs/how-to/classify-with-llm.md`.
- [x] `W03.P08.S31` - Pass the documented-command-conformance gate for the new evidence and split flags; `src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py`.
- [ ] `W03.P08.S32` - Pass the nitpicky Sphinx docs-build gate; `dev/docs/tests/test_docs_build.py`.

## Wave `W04` - Agent persona-driven manual pipeline rolling

A fresh agent persona manually rolls the complete evidence-aware LLM classification pipeline against the real implementation using the environment's authenticated cloud CLIs (antigravity/agy and codex) — not automated tests, but hands-on operator rolling of profile setup, ledger import, evidence attach, classify, saturate, and evidence-driven split. Every confusion, wrong result, or gap is captured as a tracked finding. This is the binding fallback validation the plan depends on; it amplifies coverage no unit test reaches.

### Phase `W04.P09` - Persona rolling of the evidence-aware pipeline with real cloud CLIs

An operator persona drives the shipped pipeline end to end against real authenticated cloud CLIs (antigravity/agy, codex) and real evidence, recording a testimonial and surfacing every gap as a tracked finding.

- [ ] `W04.P09.S34` - Persona setup: create a fresh profile, import a real-shaped bank statement, and attach a real purchase-invoice PDF as secure-storage evidence; `src/aeat/entrypoints/cli/_ledger.py`.
- [ ] `W04.P09.S35` - Roll classify --llm with a real cloud CLI (agy/codex) and --read-evidence --evidence-acknowledged; `confirm the model reads the invoice and the decision stamps llm provenance; `src/aeat/entrypoints/cli/_ledger.py`.
- [ ] `W04.P09.S36` - Roll classify --llm --saturate against a real cloud CLI; `confirm the model selects the IVA category, the system derives rate/base/amount, and the printed-vs-derived advisory behaves; `src/aeat/entrypoints/cli/_ledger.py`.
- [ ] `W04.P09.S37` - Roll split --llm --read-evidence --apply against a real multi-line invoice with a real cloud CLI; `confirm children sum to parent, registry-derived numbers, evidence links, and provenance; `src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`.
- [ ] `W04.P09.S38` - Capture the persona testimonial as a vault audit document and track every surfaced gap or confusion as a follow-up step with a verification gate; `.vault/audit/`.

## Description

Stage-3 of LLM ledger classification: feed a transaction's attached evidence
(purchase-invoice PDF, receipt image, email, Drive/URL document) into the existing
classify/saturate pipeline so a model reads the document to select the spending
category and IVA category and to propose an N-way split of one transaction into
several children. Authorised by the Stage-3 ADR and its research, building on the
landed Stage-1 (suggest/apply/reject) and Stage-2 (saturate: select IVA category,
derive rate/base/amount). Per the operator ruling (2026-06-10) the reader is
**on-host by default and for all serious use**, and the build order follows that:
W01 reads evidence bytes from secure storage into memory (never a temp file) and
adds the cloud-consent posture; W02 delivers the on-host text-layer reader plus the
on-host local vision reader (the `LocalAdapter` extended with the Ollama images
field and on-host PDF rasterisation) and the cache-key fix; W03 adds evidence-driven
N-way splitting. A cloud read is reachable only behind an explicit, per-invocation,
default-off, gestor-barred consent gate (in-memory HTTP only; the file-writing
CLI-agent route is excluded); it is never the default.

Every Step preserves the hard constraints from the ADR: all sensitive financial
evidence persists only in the encrypted secure-storage backend (active profile
bucket via the runtime wrapper) and is never persisted outside it (no temp files,
no plaintext side stores) - decrypted bytes exist only transiently in memory; the
LLM selects category/iva_category from the registry-grounded allow-list and proposes
split boundaries, but never emits the persisted `iva_rate`/`taxable_base`/
`iva_amount` (registry-derived; an invoice-printed figure is an advisory cross-check
only); the suggest-review-apply/reject contract and human-in-the-loop precision
safeguard hold; and a low-confidence or refused read surfaces to the operator rather
than persisting silently.

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

- Evidence bytes are read from secure storage into memory only (never a temp file),
  proven by a real-behaviour test against the secure-object path (`W01.P01.S03`).
- The cloud-upload consent gate is default-off, re-affirmed per invocation, and
  refused for a gestor context; no decrypted evidence is ever written outside secure
  storage (`W01.P02.S06`, `W02.P04.S33`).
- Extracted on-host evidence text reaches the rendered classify/saturate prompt and
  no evidence file is written outside secure storage (`W02.P03.S11`).
- The `parse_response` allow-list guard rejects out-of-allow-list category or
  iva_category from an evidence read; the printed-vs-derived IVA advisory fires on
  mismatch; applied classifications stamp `llm:<model>` plus the cited evidence id
  (`W02.P04.S16`).
- Two distinct evidence documents under the same prompt yield distinct LLM cache
  keys; the on-host local vision read (PDF rasterise plus in-memory images) returns
  a result without any byte leaving the host (`W02.P05.S19`, `W02.P05.S20`).
- The split application path enforces children-sum-to-parent and sign invariants,
  each child's regulated numbers are registry-derived (never model-emitted), and
  per-child evidence provenance survives a strict save/load roundtrip
  (`W03.P07.S29`).
- The documented-command-conformance gate passes for the new evidence and split
  flags, and the nitpicky docs-build gate passes (`W03.P08.S31`, `W03.P08.S32`).
- Across the suite, no test uses mocks, skips, xfail, or tautological assertions,
  and no path lets the LLM emit a persisted regulated tax number.
