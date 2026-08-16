---
generated: true
tags:
  - '#index'
  - '#cross-period-prorrata'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:6998ae64571f31e5442b5a4c29cf5ad3ade1a92b114d6e7e79cb57ce9c9c01a2'
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
  - '[[2026-07-06-cross-period-prorrata-W02-P03-S12]]'
  - '[[2026-07-06-cross-period-prorrata-W02-P04-S14]]'
  - '[[2026-07-06-cross-period-prorrata-W02-P04-S15]]'
  - '[[2026-07-06-cross-period-prorrata-W02-P04-S16]]'
  - '[[2026-07-06-cross-period-prorrata-W02-P04-S17]]'
  - '[[2026-07-06-cross-period-prorrata-W02-P04-S18]]'
  - '[[2026-07-06-cross-period-prorrata-W03-P05-S19]]'
  - '[[2026-07-06-cross-period-prorrata-W03-P05-S20]]'
  - '[[2026-07-06-cross-period-prorrata-W03-P05-S21]]'
  - '[[2026-07-06-cross-period-prorrata-W03-P05-S22]]'
  - '[[2026-07-06-cross-period-prorrata-W03-P05-S23]]'
  - '[[2026-07-06-cross-period-prorrata-W04-P06-S24]]'
  - '[[2026-07-06-cross-period-prorrata-W04-P06-S25]]'
  - '[[2026-07-06-cross-period-prorrata-W04-P06-S26]]'
  - '[[2026-07-06-cross-period-prorrata-W04-P06-S27]]'
  - '[[2026-07-06-cross-period-prorrata-W04-P07-S28]]'
  - '[[2026-07-06-cross-period-prorrata-W04-P07-S29]]'
  - '[[2026-07-06-cross-period-prorrata-W04-P07-S30]]'
  - '[[2026-07-06-cross-period-prorrata-W04-P07-S31]]'
  - '[[2026-07-06-cross-period-prorrata-W05-P08-S32]]'
  - '[[2026-07-06-cross-period-prorrata-W05-P08-S33]]'
  - '[[2026-07-06-cross-period-prorrata-W05-P08-S34]]'
  - '[[2026-07-06-cross-period-prorrata-W05-P08-S35]]'
  - '[[2026-07-06-cross-period-prorrata-W05-P08-S36]]'
  - '[[2026-07-06-cross-period-prorrata-W06-P09-S37]]'
  - '[[2026-07-06-cross-period-prorrata-W06-P09-S38]]'
  - '[[2026-07-06-cross-period-prorrata-W06-P09-S39]]'
  - '[[2026-07-06-cross-period-prorrata-W06-P09-S40]]'
  - '[[2026-07-06-cross-period-prorrata-W06-P09-S41]]'
  - '[[2026-07-06-cross-period-prorrata-W07-P10-S42]]'
  - '[[2026-07-06-cross-period-prorrata-W07-P10-S43]]'
  - '[[2026-07-06-cross-period-prorrata-W07-P10-S44]]'
  - '[[2026-07-06-cross-period-prorrata-W07-P11-S45]]'
  - '[[2026-07-06-cross-period-prorrata-W07-P11-S46]]'
  - '[[2026-07-06-cross-period-prorrata-W07-P12-S47]]'
  - '[[2026-07-06-cross-period-prorrata-W07-P12-S48]]'
  - '[[2026-07-06-cross-period-prorrata-W07-P12-S49]]'
  - '[[2026-07-06-cross-period-prorrata-audit]]'
  - '[[2026-07-06-cross-period-prorrata-plan]]'
  - '[[2026-07-06-cross-period-prorrata-reference]]'
  - '[[2026-07-06-cross-period-prorrata-research]]'
---

# `cross-period-prorrata` feature index

Auto-generated index of all documents tagged with `#cross-period-prorrata`.

## Documents

### adr

- `2026-07-05-cross-period-prorrata-adr` - `cross-period-prorrata` adr: `Cross-period prorrata model: provisional carry, in-year apportionment, settlement regularisation` | (**status:** `accepted`)

### audit

- `2026-07-06-cross-period-prorrata-audit` - `cross-period-prorrata` audit: `S10-S18 seed/override review`

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
- `2026-07-06-cross-period-prorrata-W02-P03-S12` - record the source observation identity on the seeded entry so the register stays cross-checkable against the prior filing forever after
- `2026-07-06-cross-period-prorrata-W02-P04-S14` - add the aeat_autorizada override entry recording the art-105.Dos AEAT-authorised provisional percentage plus its authorisation reference
- `2026-07-06-cross-period-prorrata-W02-P04-S15` - add the inicio_actividad override entry recording the art-105.Tres (via art-111.Dos) inicio-de-actividades proposed percentage plus its reference
- `2026-07-06-cross-period-prorrata-W02-P04-S16` - wire the single declared precedence ladder into the register in-force-percentage lookup so authorised/inicio provenance outranks the carried prior definitive
- `2026-07-06-cross-period-prorrata-W02-P04-S17` - surface a BLOCKING divergence finding when a carried_prior_definitiva entry contradicts the prior observation, and an informational notice naming the provenance when an aeat_autorizada or inicio_actividad entry legitimately differs from the prior definitive (never silence)
- `2026-07-06-cross-period-prorrata-W02-P04-S18` - add tests for override precedence and both observation cross-check surfaces (blocking contradiction vs informational regulated-difference notice)
- `2026-07-06-cross-period-prorrata-W03-P05-S19` - thread the register's active-general provisional percentage into the shared LedgerIvaAggregationSourceResolver deducible-cuota path so it apportions the deducible cuotas (art-104.Uno + 105.Uno), leaving bases unapportioned
- `2026-07-06-cross-period-prorrata-W03-P05-S20` - carry the applied percentage and its provenance on the binding value provenance and the casilla observation trail (binding-values-carry-provenance)
- `2026-07-06-cross-period-prorrata-W03-P05-S21` - add a byte-identical regression proving a non-prorrata (fully-taxable) taxpayer's deducible aggregation is unchanged from today
- `2026-07-06-cross-period-prorrata-W03-P05-S22` - add a field-flows test proving the provisional percentage actually reduces the deducible cuotas for a prorrata taxpayer (the apportionment bites, not dead wiring)
- `2026-07-06-cross-period-prorrata-W03-P05-S23` - add the pull==calculate parity regression proving the apportioned deducible casilla resolves identically on the calculate path and the Sheets-pull path (one-aggregation-path-pull-equals-calculate)
- `2026-07-06-cross-period-prorrata-W04-P06-S24` - feed M303 casilla 44 and M390 regularizacion projection
- `2026-07-06-cross-period-prorrata-W04-P06-S25` - project prorrata declared-volume ledger divergence advisory
- `2026-07-06-cross-period-prorrata-W04-P06-S26` - co-emit prorrata settlement register write-back
- `2026-07-06-cross-period-prorrata-W04-P06-S27` - prove prorrata settlement projection and year carry
- `2026-07-06-cross-period-prorrata-W04-P07-S28` - bundle AEAT prorrata regularizacion oracle
- `2026-07-06-cross-period-prorrata-W04-P07-S29` - prove prorrata regularizacion manual oracle
- `2026-07-06-cross-period-prorrata-W04-P07-S30` - defer prorrata source-mesh promotion pending peer WIP
- `2026-07-06-cross-period-prorrata-W04-P07-S31` - defer bienes-inversion unblock record pending source promotion
- `2026-07-06-cross-period-prorrata-W05-P08-S32` - derive prorrata applicability evidence
- `2026-07-06-cross-period-prorrata-W05-P08-S33` - emit missing prorrata carry advisory
- `2026-07-06-cross-period-prorrata-W05-P08-S34` - add the settlement-period verify ADVISORY predicate so the gate never grants verified_complete with zero findings on an applies-but-unresolved prorrata, mirroring the Modelo 200 implies_nonzero worked example (no-silent-under-declaration)
- `2026-07-06-cross-period-prorrata-W05-P08-S35` - add tests proving a mixed trader can no longer silently deduct 100% in-year, silently skip casilla 44, or silently zero the deducible side, while a fully-taxable trader keeps the art-94 full-deduction default untouched
- `2026-07-06-cross-period-prorrata-W05-P08-S36` - verify-close the silent-zero-base deferred prorrata volume rows (W01.P02.S03/S04 of the silent-zero-base plan) with an exec record referencing this feature's cross-period model as their resolution
- `2026-07-06-cross-period-prorrata-W06-P09-S37` - record the deferred prorrata especial per-input apportionment and the art-103.Dos.2 +10% mandatory-especial comparison advisory as an honest deferred Step behind the from-birth regime schema slot (needs especial to exist first)
- `2026-07-06-cross-period-prorrata-W06-P09-S38` - record the deferred sectores diferenciados per-sector registers, the art-104.Tres financial/inmobiliario special denominator, and the art-105.Cinco interrupted-activity three-year rule as noted follow-ups behind the from-birth sector schema slot
- `2026-07-06-cross-period-prorrata-W06-P09-S39` - record the deferred automatic art-104.Tres exclusion classification in the ledger rollup as a follow-up (the rollup stays a reconciliation check until it lands)
- `2026-07-06-cross-period-prorrata-W06-P09-S40` - run the independent campaign-close honesty review (vaultspec-code-reviewer against the ADR, plan, and commit range), persist it as a vault audit, and track every surfaced item as a new Step with a verification gate (aeat-campaign-close-honesty-review)
- `2026-07-06-cross-period-prorrata-W06-P09-S41` - record the `PRORRATA_REGULARIZACION` real-source provisioning blocker
- `2026-07-06-cross-period-prorrata-W07-P10-S42` - add a typed prorrata_regularizacion selector contract and selector-registry construction gate so the source is a legal DataBindingDefinition.source before any TOML binding is declared
- `2026-07-06-cross-period-prorrata-W07-P10-S43` - provision the Modelo 303 casilla 44 prorrata_regularizacion binding rows for current registry revisions, convert the target from manual to bound only with legal/source citations and formula-consumption implications proven
- `2026-07-06-cross-period-prorrata-W07-P10-S44` - ground the Modelo 390 annual regularizacion target, declare its future prorrata_regularizacion binding/export grounding, keep box 522 manual until S45/S46 materialise values, and include 522 in the annual deductible total formula
- `2026-07-06-cross-period-prorrata-W07-P11-S45` - design and implement the calculation-order seam that exposes current-year prorrata volume, definitive percentage, and deductible-total values to the prorrata_regularizacion resolver without reimplementing formula business logic
- `2026-07-06-cross-period-prorrata-W07-P11-S46` - implement the prorrata_regularizacion live source resolver with binding values, unresolved diagnostics, and provenance from the register or stamped prior observation plus current-year registry values
- `2026-07-06-cross-period-prorrata-W07-P12-S47` - enroll prorrata regularizacion in live source mesh
- `2026-07-06-cross-period-prorrata-W07-P12-S48` - re-ratify bienes inversion remaining source blocker
- `2026-07-06-cross-period-prorrata-W07-P12-S49` - run W07 promotion close review

### plan

- `2026-07-06-cross-period-prorrata-plan` - `cross-period-prorrata` plan

### reference

- `2026-07-06-cross-period-prorrata-reference` - `cross-period-prorrata` reference: `cross-period-prorrata handover: W01 landed foundation, design decisions, plan roadmap, grounding surprises for the W02+ builder`

### research

- `2026-07-06-cross-period-prorrata-research` - `cross-period-prorrata` research: `provisional carry and settlement regularisation grounding`
