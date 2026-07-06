---
generated: true
tags:
  - '#index'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-06'
related:
  - '[[2026-07-05-cross-period-prorrata-adr]]'
  - '[[2026-07-06-cross-period-prorrata-W01-P01-S01]]'
  - '[[2026-07-06-cross-period-prorrata-W01-P01-S02]]'
  - '[[2026-07-06-cross-period-prorrata-W01-P01-S03]]'
  - '[[2026-07-06-cross-period-prorrata-W01-P01-S04]]'
  - '[[2026-07-06-cross-period-prorrata-plan]]'
  - '[[2026-07-06-cross-period-prorrata-research]]'
---

# `cross-period-prorrata` feature index

Auto-generated index of all documents tagged with `#cross-period-prorrata`.

## Documents

### adr

- `2026-07-05-cross-period-prorrata-adr` - `cross-period-prorrata` adr: `Cross-period prorrata model: provisional carry, in-year apportionment, settlement regularisation` | (**status:** `accepted`)

### exec

- `2026-07-06-cross-period-prorrata-W01-P01-S01` - declare the closed ProrrataRegime (general | especial | none) and ProrrataProvisionalProvenance (carried_prior_definitiva | aeat_autorizada | inicio_actividad) StrEnums in core per the closed-value-set-in-core rule, Spanish stems
- `2026-07-06-cross-period-prorrata-W01-P01-S02` - declare the strict ProrrataRegisterEntry pydantic model (ejercicio, regime, sector axis, provisional percentage + provenance + optional authorisation reference, definitive percentage + volume inputs once settled, source-observation identity) mirroring domain/bienes_inversion shapes
- `2026-07-06-cross-period-prorrata-W01-P01-S03` - declare the ProrrataRegister aggregate holding one entry per (ejercicio, sector) with regime and sector axes present from birth so especial and sectores land without migration (no-legacy-compatibility)
- `2026-07-06-cross-period-prorrata-W01-P01-S04` - implement the pure precedence-ladder resolver (authorised/inicio provenance > carried prior definitive > no value) returning the in-force provisional percentage or None, never a fabricated default, with unit tests over the ladder

### plan

- `2026-07-06-cross-period-prorrata-plan` - `cross-period-prorrata` plan

### research

- `2026-07-06-cross-period-prorrata-research` - `cross-period-prorrata` research: `provisional carry and settlement regularisation grounding`
