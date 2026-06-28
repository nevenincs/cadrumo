---
tags:
  - '#plan'
  - '#calculation-source-connectivity'
date: '2026-05-20'
modified: '2026-05-20'
tier: L3
related:
  - '[[2026-05-20-calculation-source-connectivity-research]]'
  - '[[2026-05-20-calculation-source-connectivity-adr]]'
  - '[[2026-05-21-calculation-source-connectivity-reference]]'
---


# `calculation-source-connectivity` `source mesh implementation` plan

## Wave `W01` - foundation and default path

Build the generic source mesh contract and route the default calculation path through it before enrolling broader evidence families.

### Phase `W01.P01` - source mesh contracts

Create strict typed contracts and resolver ownership concepts without changing calculation behavior.

- [x] `W01.P01.S01` - Define strict source mesh context resolution provenance and diagnostic models; `src/aeat/application/aggregation/_source_mesh.py`.
- [x] `W01.P01.S02` - Define resolver protocol ownership and merge semantics; `src/aeat/application/aggregation/_source_mesh.py`.
- [x] `W01.P01.S03` - Export source mesh contracts from aggregation package; `src/aeat/application/aggregation/__init__.py`.
- [x] `W01.P01.S04` - Test source resolution merge rejects duplicate binding ownership; `src/aeat/application/aggregation/test_source_mesh.py`.
- [x] `W01.P01.S05` - Test source resolution merge rejects duplicate bound casilla ownership; `src/aeat/application/aggregation/test_source_mesh.py`.
- [x] `W01.P01.S06` - Test unhandled source diagnostics name modelo binding and source kind; `src/aeat/application/aggregation/test_source_mesh.py`.

### Phase `W01.P02` - existing ledger path wrapper

Wrap the current ledger IVA, Renta, and OSS paths behind the source mesh while preserving current calculations.

- [x] `W01.P02.S07` - Wrap ledger IVA binding resolution as a source mesh resolver; `src/aeat/application/aggregation/_modelo_bindings.py`.
- [x] `W01.P02.S08` - Wrap ledger Renta expense binding resolution as a source mesh resolver; `src/aeat/application/aggregation/_modelo_bindings.py`.
- [x] `W01.P02.S09` - Wrap OSS IOSS ledger binding resolution as a source mesh resolver; `src/aeat/application/aggregation/_oss_ioss.py`.
- [x] `W01.P02.S10` - Preserve IVA ledger source transaction and prorrata provenance in resolver output; `src/aeat/application/aggregation/_iva_ledger.py`.
- [x] `W01.P02.S11` - Preserve Renta purchase invoice evidence provenance in resolver output; `src/aeat/application/aggregation/_renta_ledger.py`.
- [x] `W01.P02.S12` - Test mesh wrapper parity with current bucket ledger aggregation; `src/aeat/application/aggregation/test_modelo_source_mesh_ledger.py`.

### Phase `W01.P03` - default calculation enrollment

Route the default modelo calculation entrypoint through source ownership checks and mesh-backed resolution.

- [x] `W01.P03.S13` - Replace hardcoded ledger binding ownership with resolver ownership map; `src/aeat/application/modelo/_actions.py`.
- [x] `W01.P03.S14` - Route bucket aggregation calculation through source mesh resolution; `src/aeat/application/modelo/_actions.py`.
- [x] `W01.P03.S15` - Route app modelo work calculate through mesh backed calculation; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W01.P03.S16` - Test caller binding override rejection for all resolver owned sources; `src/aeat/application/modelo/test_source_mesh_calculation.py`.
- [x] `W01.P03.S17` - Test caller casilla override rejection for all resolver owned sources; `src/aeat/application/modelo/test_source_mesh_calculation.py`.
- [x] `W01.P03.S18` - Test CLI calculation persists ledger derived source observations; `src/aeat/entrypoints/cli/test_modelo_source_mesh_calculate.py`.

## Wave `W02` - source family enrollment

Enroll the existing non-ledger source families after the default path has deterministic source ownership and collision rules.

### Phase `W02.P04` - profile previous filing and live sources

Enroll profile, previous filing, relation, borrador, and IVA wallet sources as explicit resolvers.

- [x] `W02.P04.S19` - Enroll profile bindings through a source mesh resolver; `src/aeat/application/aggregation/_source_profile.py`.
- [x] `W02.P04.S20` - Enroll previous filing values through a source mesh resolver; `src/aeat/application/calculations/_multi_year.py`.
- [x] `W02.P04.S21` - Enroll relation prefill values through a source mesh resolver; `src/aeat/application/calculations/_relation_prefill.py`.
- [x] `W02.P04.S22` - Enroll borrador Modelo 100 values through a source mesh resolver; `src/aeat/application/modelo/_borrador_binding.py`.
- [x] `W02.P04.S23` - Enroll IVA wallet decision values through a source mesh resolver; `src/aeat/application/calculations/_iva_wallet_reconciliation.py`.
- [x] `W02.P04.S24` - Test profile and live source fingerprints appear in source resolution; `src/aeat/application/aggregation/test_source_mesh_profile_live.py`.

### Phase `W02.P05` - invoice evidence and retenciones

Adapt invoice, evidence, payable, collectible, counterpart, and withholding sources into repository-backed source resolution.

- [x] `W02.P05.S25` - Adapt InvoiceCatalogue observations into source mesh resolution; `src/aeat/application/invoices/_source_resolver.py`.
- [ ] `W02.P05.S26` - Adapt purchase invoice evidence records into source mesh resolution; `src/aeat/application/ledger/_evidence.py`.
- [ ] `W02.P05.S27` - Adapt payable invoice records into source mesh resolution; `src/aeat/application/ledger/_business_operation_invoice.py`.
- [ ] `W02.P05.S28` - Adapt collectible invoice records into source mesh resolution; `src/aeat/application/ledger/_business_operation_invoice.py`.
- [ ] `W02.P05.S29` - Enroll counterpart aggregation registry provider through source mesh; `src/aeat/application/aggregation/_registry_provider.py`.
- [ ] `W02.P05.S30` - Enroll retenciones aggregation through repository backed source resolution; `src/aeat/application/aggregation/_retenciones.py`.
- [ ] `W02.P05.S31` - Test invoice ledger cross references produce stable source refs; `src/aeat/application/aggregation/test_source_mesh_invoices.py`.
- [ ] `W02.P05.S32` - Test retenciones source observations are period and source kind filtered; `src/aeat/application/aggregation/test_source_mesh_retenciones.py`.

## Wave `W03` - domain expansion gates

Prepare region-aware Renta, fincas, and inventory source enrollment without bypassing storage or provenance hardening.

### Phase `W03.P06` - renta regional context

Make deductible expense context region-aware only where the data model and category profiles support it.

- [ ] `W03.P06.S33` - Add region field to Renta deductibility context when category profiles require it; `src/aeat/domain/renta/_ledger_expenses.py`.
- [ ] `W03.P06.S34` - Extend category profile lookup to accept filing year and CCAA key; `src/aeat/core/resources/_repos/category_profiles.py`.
- [ ] `W03.P06.S35` - Represent region scoped category profiles in registry resources; `src/aeat/_data/registry/aeat/categories/profiles`.
- [ ] `W03.P06.S36` - Derive Renta source region from TaxResidenceProfile CCAA; `src/aeat/application/aggregation/_renta_ledger.py`.
- [ ] `W03.P06.S37` - Test non regional category profiles preserve existing Renta results; `src/aeat/application/aggregation/test_renta_ledger.py`.
- [ ] `W03.P06.S38` - Test region scoped category profiles select by profile CCAA; `src/aeat/application/aggregation/test_renta_ledger_region.py`.

### Phase `W03.P07` - fincas and inventory readiness

Define resolver readiness gates for property and inventory sources before calculation enrollment.

- [ ] `W03.P07.S39` - Define fincas calculation source readiness diagnostics; `src/aeat/domain/fincas/_source_readiness.py`.
- [ ] `W03.P07.S40` - Define fincas resolver adapter boundaries without enrolling calculations; `src/aeat/application/aggregation/_source_fincas.py`.
- [ ] `W03.P07.S41` - Define inventory calculation source readiness diagnostics; `src/aeat/application/inventory/_source_readiness.py`.
- [ ] `W03.P07.S42` - Define inventory resolver adapter boundaries without enrolling calculations; `src/aeat/application/aggregation/_source_inventory.py`.
- [ ] `W03.P07.S43` - Test fincas and inventory resolvers emit blocked readiness diagnostics; `src/aeat/application/aggregation/test_source_mesh_readiness.py`.

## Wave `W04` - verification and rollout

Add registry connectivity checks, CLI regression coverage, approval staleness fingerprints, and documentation for the mesh rollout.

### Phase `W04.P08` - connectivity validation

Prevent silent all-zero outputs by validating every registry source against resolver enrollment or explicit manual status.

- [ ] `W04.P08.S44` - Add registry source enrollment report for every committed modelo revision; `src/aeat/domain/calculations/registry/_queries.py`.
- [ ] `W04.P08.S45` - Validate every source backed binding is resolved manual or explicitly blocked; `src/aeat/application/aggregation/_source_mesh.py`.
- [ ] `W04.P08.S46` - Expose missing source diagnostics in modelo calculation errors; `src/aeat/application/modelo/_actions.py`.
- [ ] `W04.P08.S47` - Test committed modelo source inventory against enrolled resolvers; `src/aeat/domain/calculations/registry/test_source_enrollment.py`.
- [ ] `W04.P08.S48` - Test missing source backed bindings cannot silently calculate zero; `src/aeat/application/modelo/test_source_mesh_missing_sources.py`.

### Phase `W04.P09` - operator regression and audit

Verify real operator flows and calculation provenance with repository-backed tests and approval-basis coverage.

- [ ] `W04.P09.S49` - Include resolver fingerprints in approval basis; `src/aeat/application/filing/_review.py`.
- [ ] `W04.P09.S50` - Persist source refs and fingerprints on calculation revisions; `src/aeat/domain/modelos/_calculation.py`.
- [ ] `W04.P09.S51` - Emit bucket events with source mesh diagnostics and fingerprints; `src/aeat/application/modelo/_actions.py`.
- [ ] `W04.P09.S52` - Test approval staleness changes when invoice source data changes; `src/aeat/application/filing/test_source_mesh_review.py`.
- [ ] `W04.P09.S53` - Test calculation revision roundtrip preserves source refs; `src/aeat/application/modelo/test_source_mesh_revision_roundtrip.py`.
- [ ] `W04.P09.S54` - Run feature surface quality gate for source mesh touched files; `.agents/skills/feature-surface-gate/SKILL.md`.

## Wave `W05` - continuous discovery hardening and review

Keep the plan open to newly discovered calculation source surfaces and require code review audit and hardening passes before completion.

### Phase `W05.P10` - expansion governance

Re-run source discovery during implementation and extend this plan whenever a relevant unenrolled surface is found.

- [ ] `W05.P10.S55` - Re-run registry source inventory after each implementation wave; `src/aeat/_data/registry/aeat/modelos`.
- [ ] `W05.P10.S56` - Extend plan rows for newly discovered unenrolled source surfaces; `.vault/plan/2026-05-20-calculation-source-connectivity-plan.md`.
- [ ] `W05.P10.S57` - Document discovered source surfaces in execution records; `.vault/exec/2026-05-20-calculation-source-connectivity`.

### Phase `W05.P11` - review audit and hardening

Review each implemented wave for architectural drift missing provenance stale fingerprints and unsafe silent calculation behavior.

- [ ] `W05.P11.S58` - Run code review after each completed implementation wave; `.agents/skills/vaultspec-code-review/SKILL.md`.
- [ ] `W05.P11.S59` - Run architecture boundary audit for source mesh directionality; `src/aeat/application/aggregation`.
- [ ] `W05.P11.S60` - Run calculation grounding audit for provenance and legal refs; `src/aeat/application/modelo`.
- [ ] `W05.P11.S61` - Run hardening pass for silent zero and missing source diagnostics; `src/aeat/domain/calculations/registry`.
