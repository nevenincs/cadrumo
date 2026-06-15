---
tags:
  - '#plan'
  - '#legal-grounding-centralization'
date: '2026-06-14'
modified: '2026-06-15'
tier: L2
related:
  - '[[2026-06-14-legal-grounding-centralization-audit]]'
  - '[[2026-06-14-legal-grounding-centralization-adr]]'
  - '[[2026-06-14-legal-grounding-centralization-research]]'
---
# `legal-grounding-centralization` plan

### Phase `P01` - Safe pure-centralization (value unchanged)

Promote inline-grounded regulatory values to the central authority without changing the value — only its home. Lowest regression risk: each move is value-identical and lands with a grounding/roundtrip assertion. Covers F6 (art.58/59 family thresholds), F5 (DT12 40% + SAL 10%/2x), and F2-interim (prorrata art.103.Dos/art.9.1.c thresholds).



- [x] `P01.S01` - F6: promote LIRPF art.58/59 family thresholds (max-age 25, max-age 3, custodia 0.5) to external_constants grounded on the cited articles; `src/aeat/domain/contribuyente/family.py`.
- [x] `P01.S02` - F5: promote DT12 40% rescate reducción and Ley 44/2015 SAL 10% dotación + 2x cap factor to registry/external_constants with legal_refs->corpus_ref; `src/aeat/domain/modelos/_dt12_reduccion.py`.
- [x] `P01.S03` - F2-interim: promote prorrata art.103.Dos (1.10) and art.9.1.c (50pp) thresholds to external_constants with legal_refs, value-identical; `src/aeat/domain/iva/_prorrata.py`.

### Phase `P02` - Live calc-path wiring with parity proof

Wire the dormant registry reader into the live calculation dispatch so the registry parameter becomes causal. Higher value, higher risk: the value reaches a real filing amount, so each wiring lands only with a parity proof against the existing oracle tests. Covers F1 (art.23.2 tier reducción).

- [x] `P02.S04` - F1: wire resolve_reduccion to the dormant _resolve_tier_reduccion_rate registry reader; `constant becomes documented fallback; prove parity against tier oracle tests; `src/aeat/domain/fincas/_tier_resolver.py`.

### Phase `P03` - Dormant/duplicate routing resolution

Resolve dormant or inline casilla-routing per no-legacy-compatibility: bind through the registry OR delete the dormant capacity, never leave live-but-unrouted. Covers F3 (M303/M390 compensación casilla routing), F4 (casilla_59/60 helpers), and the F2 final routing decision for the prorrata subsystem.

- [x] `P03.S05` - F3: resolve M303/M390 compensación casilla ids through the registry snapshot casilla definitions instead of inline numeric literals; `src/aeat/application/calculations/_iva_compensation_history.py`.
- [x] `P03.S06` - F4: author the ledger_iva_aggregation base_amount_sum bindings (INTRA_COMMUNITY_SUPPLY->59, EXPORT_THIRD_COUNTRY_ZERO_RATED->60) and delete the dormant casilla_59/60 Python helpers; `src/aeat/application/aggregation/_iva_ledger.py`.
- [x] `P03.S07` - F2-final: decide prorrata subsystem fate — enroll as registry-declared aggregation source on 303/390 casillas OR delete the dormant subsystem per no-legacy-compatibility; `src/aeat/domain/iva/_prorrata.py`.

## Description


## Steps







## Parallelization


## Verification

