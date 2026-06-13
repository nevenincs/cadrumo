---
tags:
  - '#plan'
  - '#llm-ledger-classification'
date: '2026-06-03'
modified: '2026-06-03'
tier: L2
related:
  - '[[2026-06-03-llm-ledger-classification-adr]]'
  - '[[2026-06-03-llm-ledger-classification-research]]'
---


# `llm-ledger-classification` `Wire LLM-assisted ledger classification (MVP): application use case, CLI surface, tests, docs` plan

### Phase `P01` - Application layer: suggest, apply, provider availability

Wire the existing classifier into application use cases without persisting on suggest.

- [x] `P01.S01` - Add an application use case that runs the LLM classifier for one transaction and returns a typed suggestion without persisting; `src/aeat/application/ledger/`.
- [x] `P01.S02` - Add an apply path that persists an accepted LLM suggestion through the existing manual-classify write with llm: provenance and recorded confidence and reason; `src/aeat/application/ledger/`.
- [x] `P01.S03` - Resolve and report which subprocess LLM providers are available on PATH; `src/aeat/application/ledger/`.

### Phase `P02` - Operator CLI surface

Expose the suggest/apply loop on aeat app ledger classify with override and reject.

- [x] `P02.S04` - Extend aeat app ledger classify with --llm provider preview-by-default and --apply to persist, reusing manual classify as override and no-apply as reject; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `P02.S05` - Surface provider availability and refuse instructively when the chosen provider is unavailable; `src/aeat/entrypoints/cli/_ledger.py`.

### Phase `P03` - Tests, documentation, verification

Lock the contract with real-behavior tests, document the surface, and verify with a naive persona.

- [x] `P03.S06` - Add real-behavior tests for suggest, apply-persists-llm-provenance, manual-override-wins, reject-leaves-unchanged, and unavailable-provider refusal; `src/aeat/entrypoints/cli/`.
- [x] `P03.S07` - Author a how-to for LLM-assisted classification and keep the command-validation gate green; `docs/how-to/`.
- [x] `P03.S08` - Re-run a naive persona to confirm leverage, override, and reject end to end; `docs/`.

## Description


## Steps







## Parallelization


## Verification
