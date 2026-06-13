---
tags:
  - '#plan'
  - '#llm-evidence-classification'
date: '2026-06-13'
modified: '2026-06-13'
tier: L3
related:
  - '[[2026-06-10-llm-evidence-classification-adr]]'
  - '[[2026-06-13-llm-evidence-classification-audit]]'
  - '[[2026-06-10-llm-evidence-classification-research]]'
---
<!-- RETIRED: W04, W05, W06, W07 -->







# `llm-evidence-classification` `Evidence corpus and adversarial hardening` plan

## Wave `W01` - Classify provider-optional UX

Make --llm optional when --read-evidence routes scan/image evidence to the on-host vision model; require a provider only for the text/cloud path.


### Phase `W01.P01` - Provider-optional classify/saturate/split

Thread provider Optional with lazy text-classifier resolution; route --read-evidence into the LLM path; instructive refusal when the text path needs a provider.

- [x] `W01.P01.S01` - Thread provider Optional with lazy text-classifier resolution in suggest/saturate/split classification; `src/aeat/application/ledger/_llm_classification.py`.
- [x] `W01.P01.S02` - Route --read-evidence into the LLM path when --llm is absent; `refuse instructively when the text path needs a provider; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W01.P01.S03` - Test image evidence without --llm classifies via the vision model and text/no-evidence without --llm refuses instructively; `src/aeat/application/ledger/tests/test_llm_vision_evidence.py`.

## Wave `W02` - Evidence corpus sourcing

Source licence-clean, PII-free sample invoices (text-layer PDF, scanned/image PDF, image) to fixtures with provenance sidecars, plus generated adversarial variants.

### Phase `W02.P02` - Corpus and provenance

Source real licence-clean invoices to fixtures with provenance sidecars and adversarial variants.

- [x] `W02.P02.S04` - Source licence-clean text-layer PDF, scanned/image PDF, and image invoices into a fixtures corpus; `src/aeat/application/ledger/tests/_evidence_corpus/`.
- [x] `W02.P02.S05` - Write a provenance sidecar per corpus fixture declaring real_corpus or synthetic_generated and its source; `src/aeat/application/ledger/tests/_evidence_corpus/`.
- [x] `W02.P02.S06` - Generate adversarial fixture variants (prompt-injection invoice, malformed/empty PDF, multi-page, foreign-language); `src/aeat/application/ledger/tests/_evidence_corpus/`.

## Wave `W03` - Adversarial testing

Adversarially test evidence parsing (text-layer, rasterise, vision dispatch) and the allow-list parser against the corpus and hostile inputs.

### Phase `W03.P03` - Adversarial parsing tests

Adversarial tests for evidence parsing and the allow-list parser against the corpus and hostile inputs.

- [x] `W03.P03.S07` - Adversarially test evidence parsing (text-layer, in-memory rasterise, vision dispatch) against the corpus; `src/aeat/application/ledger/tests/test_evidence_corpus_parsing.py`.
- [x] `W03.P03.S08` - Adversarially test parse_response: prompt-injection JSON, hostile/oversized output, out-of-allow-list values are rejected; `src/aeat/domain/transactions/tests/test_llm_parse_adversarial.py`.

## Description


## Steps







## Parallelization


## Verification

