---
tags:
  - '#plan'
  - '#modelo-151-beckham-source-scope'
date: '2026-07-01'
modified: '2026-07-17'
body_hash: 'sha256:f46773c0261583110401c58c47c84526151cbbdfc41e8002409f3cb6e33e2293'
tier: L2
related:
  - '[[2026-07-01-modelo-151-beckham-source-scope-adr]]'
  - '[[2026-07-10-modelo-151-beckham-source-scope-research]]'
---

# `modelo-151-beckham-source-scope` plan

### Phase `P01` - Impatriado ES-source income classifier and base binding

Consume the source_jurisdiction axis: fold ES-source income into impatriado.base-liquidable-general, segregate foreign/unresolved rows

- [x] `P01.S01` - Add ledger_impatriado_income_aggregation source kind, ES-source classifier, M151 base binding, mesh resolver + enrollment, and non-tautological tests (ES folds in, foreign segregated, None fails loud, trabajo admitted); `src/aeat/core/aggregation.py,src/aeat/application/aggregation/_impatriado_income_ledger.py,src/aeat/domain/calculations/registry/_ledger_bindings.py,src/aeat/_data/registry/aeat/modelos/151`.

### Phase `P02` - Savings escala (deferred, corpus-first)

Ingest art. 93.2.e.2 / art. 25.1.f TRLIRNR savings-band schedule and add the source-scoped base del ahorro

- [x] `P02.S02` - Ingest the art. 93.2.e.2 savings-band corpus and add the source-scoped base del ahorro and its escala; `src/aeat/_data/corpus/normatives/html,src/aeat/_data/registry/aeat/modelos/151`.

## Description

## Steps

## Parallelization

## Verification
