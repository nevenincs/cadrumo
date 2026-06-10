---
tags:
  - '#plan'
  - '#llm-ledger-classification'
date: '2026-06-04'
tier: L2
related:
  - '[[2026-06-04-llm-ledger-classification-adr]]'
  - '[[2026-06-03-llm-ledger-classification-research]]'
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

# `llm-ledger-classification` `Saturate transactions with grounded rich tax metadata (stage 2): primitives, schema, saturate path, review` plan

### Phase `P01` - Grounded domain primitives

Author the IvaCategory rate resolver, the inverse-split utility, and the gross=base+iva invariant in domain.iva / Transaction.

- [x] `P01.S01` - Add an IvaCategory to rate-kind to lookup_rate resolver in domain.iva (zero/exempt derive zero; `non-derivable categories surfaced, not guessed); `src/aeat/domain/iva/`.
- [x] `P01.S02` - Promote the inverse-split utility gross+rate to base+iva into domain.iva using core.money.round_to_cents; `src/aeat/domain/iva/`.
- [x] `P01.S03` - Add a gross equals base plus iva consistency invariant on the Transaction model to the cent; `src/aeat/domain/transactions/_models.py`.

### Phase `P02` - Extend the LLM classifier schema and prompt

Add iva_category selection from a grounded allow-list, hallucination-guarded; no numeric tax fields on the response.

- [x] `P02.S04` - Extend LLMClassificationResponse with iva_category and proposed business_pct, build a grounded IVA-category allow-list in PromptSpec, and extend the parse_response hallucination guard; `src/aeat/domain/transactions/_llm.py`.

### Phase `P03` - Saturate application path and CLI

Compose classify + rate lookup + derivation into a saturated suggestion; persist via the manual-command write with provenance and override/reject.

- [x] `P03.S05` - Add a saturate application path that runs the classifier, looks up the rate for the selected IVA category, derives base and amount, and returns a full suggestion with llm and derived provenance; `src/aeat/application/ledger/_llm_classification.py`.
- [x] `P03.S06` - Persist a saturated suggestion through the manual-command write with the invariant; `support per-field manual override and reject; `src/aeat/entrypoints/cli/_ledger.py`.

### Phase `P04` - Tests, peer review, persona, verification

Lock the contract with real-behavior tests, peer-review, persona-test, and verify functional.

- [x] `P04.S07` - Add real-behavior tests for saturate suggest, apply with provenance and invariant, per-field override, non-derivable category surfacing, and hallucination-guard rejection; `src/aeat/entrypoints/cli/`.
- [x] `P04.S08` - Peer-review the saturation pipeline with the code-reviewer and absorb findings; `src/aeat/`.
- [x] `P04.S09` - Persona-test and document the saturation surface and keep the command-validation gate green; `docs/how-to/`.

## Description


## Steps







## Parallelization


## Verification
