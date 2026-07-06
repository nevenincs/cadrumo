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
  - '[[2026-07-06-cross-period-prorrata-W01-P02-S05]]'
  - '[[2026-07-06-cross-period-prorrata-W01-P02-S06]]'
  - '[[2026-07-06-cross-period-prorrata-W01-P02-S07]]'
  - '[[2026-07-06-cross-period-prorrata-W01-P02-S08]]'
  - '[[2026-07-06-cross-period-prorrata-W01-P02-S09]]'
  - '[[2026-07-06-cross-period-prorrata-W02-P03-S10]]'
  - '[[2026-07-06-cross-period-prorrata-W02-P03-S11]]'
  - '[[2026-07-06-cross-period-prorrata-W02-P03-S12]]'
  - '[[2026-07-06-cross-period-prorrata-audit]]'
  - '[[2026-07-06-cross-period-prorrata-plan]]'
  - '[[2026-07-06-cross-period-prorrata-research]]'
---

# `cross-period-prorrata` feature index

Auto-generated index of all documents tagged with `#cross-period-prorrata`.

## Documents

### adr

- `2026-07-05-cross-period-prorrata-adr` - `cross-period-prorrata` adr: `Cross-period prorrata model: provisional carry, in-year apportionment, settlement regularisation` | (**status:** `accepted`)

### audit

- `2026-07-06-cross-period-prorrata-audit` - `cross-period-prorrata` audit: `S10-S12 seed review`

### exec

- `2026-07-06-cross-period-prorrata-W01-P01-S01` - declare the closed ProrrataRegime (general | especial | none) and ProrrataProvisionalProvenance (carried_prior_definitiva | aeat_autorizada | inicio_actividad) StrEnums in core per the closed-value-set-in-core rule, Spanish stems
- `2026-07-06-cross-period-prorrata-W01-P01-S02` - declare the strict ProrrataRegisterEntry pydantic model (ejercicio, regime, sector axis, provisional percentage + provenance + optional authorisation reference, definitive percentage + volume inputs once settled, source-observation identity) mirroring domain/bienes_inversion shapes
- `2026-07-06-cross-period-prorrata-W01-P01-S03` - declare the ProrrataRegister aggregate holding one entry per (ejercicio, sector) with regime and sector axes present from birth so especial and sectores land without migration (no-legacy-compatibility)
- `2026-07-06-cross-period-prorrata-W01-P01-S04` - implement the pure precedence-ladder resolver (authorised/inicio provenance > carried prior definitive > no value) returning the in-force provisional percentage or None, never a fabricated default, with unit tests over the ladder
- `2026-07-06-cross-period-prorrata-W01-P02-S05` - declare the PROFILE_PRORRATA_REGISTER FINANCIAL bucket-local secure-object namespace singleton and export it from the storage facade, mirroring PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE
- `2026-07-06-cross-period-prorrata-W01-P02-S06` - implement the encrypted ProrrataRegisterRepository (governed singleton save/load through SecureObjectRepository) on the bienes_inversion adapter pattern
- `2026-07-06-cross-period-prorrata-W01-P02-S07` - add the application service facade to declare, list, and get the per-ejercicio register entry, exposed only through the package top-level __all__
- `2026-07-06-cross-period-prorrata-W01-P02-S08` - add the strict save/load/equality roundtrip test with every defaultable field populated non-default, using the real EphemeralMasterKeyProvider and SQLite engine (aeat-roundtrip-discipline)
- `2026-07-06-cross-period-prorrata-W01-P02-S09` - add the anti-tautology corrupt-payload proof: mutate the on-disk register to delete a field, reload, assert ValidationError or strict inequality surfaces
- `2026-07-06-cross-period-prorrata-W02-P03-S10` - implement the seed function: resolve the prior settlement revision via select_revision(M303, ejercicio-1, settlement period), read the iva.prorrata-porcentaje observation, and re-confirm its stamped_revision_id before seeding the carried_prior_definitiva entry
- `2026-07-06-cross-period-prorrata-W02-P03-S11` - make a divergent stamped_revision_id block the seed with a REGISTRY_REVISION_DIVERGENCE-class finding and a missing legacy stamp surface a non-blocking advisory, never silence (carried-observations-stamp-their-revision)
- `2026-07-06-cross-period-prorrata-W02-P03-S12` - record the source observation identity on the seeded entry so the register stays cross-checkable against the prior filing forever after

### plan

- `2026-07-06-cross-period-prorrata-plan` - `cross-period-prorrata` plan

### research

- `2026-07-06-cross-period-prorrata-research` - `cross-period-prorrata` research: `provisional carry and settlement regularisation grounding`
