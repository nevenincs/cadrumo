---
tags:
  - '#plan'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-08'
tier: L3
related:
  - '[[2026-07-05-cross-period-prorrata-adr]]'
  - '[[2026-07-01-iva-complexity-hardening-scope-adr]]'
  - '[[2026-06-19-silent-zero-base-aggregation-plan]]'
  - '[[2026-07-05-silent-zero-base-aggregation-audit]]'
  - '[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr]]'
  - '[[2026-07-01-iva-bienes-inversion-regularizacion-adr]]'
  - '[[2026-07-06-cross-period-prorrata-research]]'
---
# `cross-period-prorrata` plan

## Wave `W01` - Register foundation (the carry home)

Land the per-ejercicio ProrrataRegister typed model and its encrypted profile-scoped persistence on the bienes-inversion register pattern, with regime and sector axes present from birth (no-legacy-compatibility). Persistence boundary: full aeat-roundtrip-discipline (save/load/equality with every field non-default, plus anti-tautology corrupt-payload proof). Executor: vaultspec-standard-executor.

### Phase `W01.P01` - Domain model

The ProrrataRegister aggregate, per-ejercicio entry model, closed regime and provenance enums, and the pure precedence-ladder resolver, mirroring domain/bienes_inversion shapes.

- [x] `W01.P01.S01` - declare the closed ProrrataRegime (general | especial | none) and ProrrataProvisionalProvenance (carried_prior_definitiva | aeat_autorizada | inicio_actividad) StrEnums in core per the closed-value-set-in-core rule, Spanish stems; `src/aeat/core/__init__.py`.
- [x] `W01.P01.S02` - declare the strict ProrrataRegisterEntry pydantic model (ejercicio, regime, sector axis, provisional percentage + provenance + optional authorisation reference, definitive percentage + volume inputs once settled, source-observation identity) mirroring domain/bienes_inversion shapes; `src/aeat/domain/prorrata_register/__init__.py`.
- [x] `W01.P01.S03` - declare the ProrrataRegister aggregate holding one entry per (ejercicio, sector) with regime and sector axes present from birth so especial and sectores land without migration (no-legacy-compatibility); `src/aeat/domain/prorrata_register/__init__.py`.
- [x] `W01.P01.S04` - implement the pure precedence-ladder resolver (authorised/inicio provenance > carried prior definitive > no value) returning the in-force provisional percentage or None, never a fabricated default, with unit tests over the ladder; `src/aeat/domain/prorrata_register/tests/test_prorrata_register.py`.

### Phase `W01.P02` - Encrypted persistence and roundtrip discipline

The PROFILE_* secure-object namespace, the FINANCIAL singleton repository, the application service facade, and the full roundtrip + anti-tautology proof for the persistence boundary.

- [x] `W01.P02.S05` - declare the PROFILE_PRORRATA_REGISTER FINANCIAL bucket-local secure-object namespace singleton and export it from the storage facade, mirroring PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE; `src/aeat/adapters/persistence/storage/_namespace_registry.py`.
- [x] `W01.P02.S06` - implement the encrypted ProrrataRegisterRepository (governed singleton save/load through SecureObjectRepository) on the bienes_inversion adapter pattern; `src/aeat/adapters/persistence/profile/prorrata_register.py`.
- [x] `W01.P02.S07` - add the application service facade to declare, list, and get the per-ejercicio register entry, exposed only through the package top-level __all__; `src/aeat/application/prorrata_register/__init__.py`.
- [x] `W01.P02.S08` - add the strict save/load/equality roundtrip test with every defaultable field populated non-default, using the real EphemeralMasterKeyProvider and SQLite engine (aeat-roundtrip-discipline); `src/aeat/adapters/persistence/profile/tests/test_prorrata_register_roundtrip.py`.
- [x] `W01.P02.S09` - add the anti-tautology corrupt-payload proof: mutate the on-disk register to delete a field, reload, assert ValidationError or strict inequality surfaces; `src/aeat/adapters/persistence/profile/tests/test_prorrata_register_roundtrip.py`.

## Wave `W02` - Provisional seed (the cross-year carry)

Seed the carried_prior_definitiva entry from the stamped prior settlement observation via select_revision + stamped_revision_id re-confirmation (divergence blocks, missing legacy stamp advises), and record the art-105.Dos aeat_autorizada and art-105.Tres inicio_actividad provenance-tagged overrides. Single declared precedence ladder; no fabricated default percentage. Executor: vaultspec-high-executor (core carry logic).

### Phase `W02.P03` - Seed from stamped prior observation

The carried_prior_definitiva seed via select_revision + stamped_revision_id re-confirmation, with divergence blocking and missing-stamp advisory.

- [x] `W02.P03.S10` - implement the seed function: resolve the prior settlement revision via select_revision(M303, ejercicio-1, settlement period), read the iva.prorrata-porcentaje observation, and re-confirm its stamped_revision_id before seeding the carried_prior_definitiva entry; `src/aeat/application/prorrata_register/_seed.py`.
- [x] `W02.P03.S11` - make a divergent stamped_revision_id block the seed with a REGISTRY_REVISION_DIVERGENCE-class finding and a missing legacy stamp surface a non-blocking advisory, never silence (carried-observations-stamp-their-revision); `src/aeat/application/prorrata_register/_seed.py`.
- [x] `W02.P03.S12` - record the source observation identity on the seeded entry so the register stays cross-checkable against the prior filing forever after; `src/aeat/application/prorrata_register/_seed.py`.
- [x] `W02.P03.S13` - add tests for the seed happy path, divergence-blocks, and missing-stamp-advises paths against real filed observations; `src/aeat/application/prorrata_register/tests/test_seed.py`.

### Phase `W02.P04` - Provenance overrides and precedence

The art-105.Dos aeat_autorizada and art-105.Tres inicio_actividad override entries with authorisation reference, the single declared precedence ladder, and the observation cross-check surfaces.

- [x] `W02.P04.S14` - add the aeat_autorizada override entry recording the art-105.Dos AEAT-authorised provisional percentage plus its authorisation reference; `src/aeat/application/prorrata_register/__init__.py`.
- [x] `W02.P04.S15` - add the inicio_actividad override entry recording the art-105.Tres (via art-111.Dos) inicio-de-actividades proposed percentage plus its reference; `src/aeat/application/prorrata_register/__init__.py`.
- [x] `W02.P04.S16` - wire the single declared precedence ladder into the register in-force-percentage lookup so authorised/inicio provenance outranks the carried prior definitive; `src/aeat/application/prorrata_register/__init__.py`.
- [x] `W02.P04.S17` - surface a BLOCKING divergence finding when a carried_prior_definitiva entry contradicts the prior observation, and an informational notice naming the provenance when an aeat_autorizada or inicio_actividad entry legitimately differs from the prior definitive (never silence); `src/aeat/application/prorrata_register/_seed.py`.
- [x] `W02.P04.S18` - add tests for override precedence and both observation cross-check surfaces (blocking contradiction vs informational regulated-difference notice); `src/aeat/application/prorrata_register/tests/test_overrides.py`.

## Wave `W03` - In-year apportionment (1T-3T and every non-settlement period)

Apply the register's provisional percentage to the deducible cuotas inside the one shared ledger IVA aggregation path (art-104.Uno + 105.Uno), bases unapportioned, provenance carried on the binding value. Non-prorrata taxpayers byte-identical. Executor: vaultspec-high-executor (one-aggregation-path, core).

### Phase `W03.P05` - Provisional apportionment in the shared aggregation path

Thread the register provisional percentage into the one shared ledger IVA deducible aggregation, apportioning cuotas (not bases), with provenance carried and non-prorrata byte-identical, proven by parity and field-flows regressions.

- [x] `W03.P05.S19` - thread the register's active-general provisional percentage into the shared LedgerIvaAggregationSourceResolver deducible-cuota path so it apportions the deducible cuotas (art-104.Uno + 105.Uno), leaving bases unapportioned; `src/aeat/application/aggregation/_iva_ledger.py`.
- [x] `W03.P05.S20` - carry the applied percentage and its provenance on the binding value provenance and the casilla observation trail (binding-values-carry-provenance); `src/aeat/application/aggregation/_modelo_bindings.py`.
- [x] `W03.P05.S21` - add a byte-identical regression proving a non-prorrata (fully-taxable) taxpayer's deducible aggregation is unchanged from today; `src/aeat/application/aggregation/tests/test_iva_ledger_prorrata_apportionment.py`.
- [x] `W03.P05.S22` - add a field-flows test proving the provisional percentage actually reduces the deducible cuotas for a prorrata taxpayer (the apportionment bites, not dead wiring); `src/aeat/application/aggregation/tests/test_iva_ledger_prorrata_apportionment.py`.
- [x] `W03.P05.S23` - add the pull==calculate parity regression proving the apportioned deducible casilla resolves identically on the calculate path and the Sheets-pull path (one-aggregation-path-pull-equals-calculate); `src/aeat/application/calculations/tests/test_pull_path_calculate_path_casilla_parity.py`.

## Wave `W04` - Settlement regularisación, oracle proof, and source-kind promotion

Feed casilla 44 and the M390 annual field from compute_regularizacion_prorrata_anual over operator-declared annual volumes (authority unchanged); compute the ledger annual rollup windowed by Period.contains as a non-blocking divergence advisory only; write the definitive percentage + volume inputs back to the register on settlement (co-travelling with revision persistence, rebuildable). Promotion of PRORRATA_REGULARIZACION stays DEFERRED behind its gate until an E2E test proves the chain against a BUNDLED AEAT Manual practico IVA oracle (no fabricated expected values). Executor: vaultspec-high-executor.

### Phase `W04.P06` - Definitive, regularisación, and write-back

Feed casilla 44 and the M390 annual field from compute_regularizacion_prorrata_anual over declared volumes, compute the ledger rollup as divergence advisory, and write the definitiva + volume inputs back to the register on settlement, co-travelling with revision persistence.

- [x] `W04.P06.S24` - feed Modelo 303 casilla 44 and the Modelo 390 annual regularisación field from compute_regularizacion_prorrata_anual over the operator-declared annual volume casillas (existing registry authority unchanged), reusing the build_prorrata_regularizacion_advisory projection; `src/aeat/application/calculations/_prorrata_regularizacion.py`.
- [x] `W04.P06.S25` - compute the annual con-derecho/sin-derecho ledger rollup windowed by Period.contains over the ejercicio's periods and raise a non-blocking divergence advisory when it contradicts the declared volumes (declared volumes stay authoritative); `src/aeat/application/calculations/_prorrata_regularizacion.py`.
- [x] `W04.P06.S26` - write the definitive percentage and its volume inputs back to the register on settlement, co-travelling with revision persistence (participation-index co-write pattern) so the register is rebuildable from the observation catalogue and seeds year+1; `src/aeat/application/modelo/_revision_persistence.py`.
- [x] `W04.P06.S27` - add tests proving casilla 44 is fed from the declared-volume definitive percentage, the ledger-rollup divergence advisory fires on contradiction, and the settlement write-back seeds the year+1 carried_prior_definitiva entry; `src/aeat/application/calculations/tests/test_prorrata_regularizacion.py`.

### Phase `W04.P07` - Oracle proof and source-kind promotion

Bundle the AEAT Manual practico IVA worked example, prove the apportionment + regularisación chain end to end against it (no fabricated expected values), then promote PRORRATA_REGULARIZACION (enroll resolver + flip disposition registry in one change) and record the bienes-inversion casilla-43 unblock follow-up.

- [x] `W04.P07.S28` - source and bundle the AEAT Manual practico IVA prorrata worked example as an oracle payload (expected_by_casilla_id with a raw_evidence_locator, verbatim figures, no fabrication) under the manual_oracles corpus; `src/aeat/_data/corpus/manual_oracles/modelo-303-prorrata-general-regularizacion.json`.
- [x] `W04.P07.S29` - add the end-to-end oracle-proof test seeding the manual's raw inputs and proving the apportionment + regularisación chain independently reproduces the bundled casilla figures (no-tautological-calculation-tests, verification-grounding-needs-oracle-evidence); `src/aeat/application/calculations/tests/test_prorrata_regularizacion_oracle.py`.
- [x] `W04.P07.S30` - promote PRORRATA_REGULARIZACION from DEFERRED to a live mesh binding - enroll the resolver in merge_source_resolutions and flip the DEFERRED_SOURCE_KIND_TARGETS disposition in one change, gated on the oracle proof (no-dormant-source-resolvers), following the iva_compensation_annual_partition precedent; `src/aeat/application/aggregation/_source_mesh.py`.
- [x] `W04.P07.S31` - record the bienes-inversion automatic casilla-43 feed (BIENES_INVERSION_REGULARIZACION, promotion_depends_on) unblock as a tracked follow-up now that the definitive-percentage source exists; `src/aeat/application/aggregation/_source_mesh.py`.

## Wave `W05` - Silent-zero-base resolution and non-silence

Derive prorrata applicability fail-closed-to-visible (register active OR sin-derecho volumes present); when prorrata applies and no provisional percentage resolves through the ladder, emit a per-period calculate advisory and a settlement-period verify ADVISORY finding so the gate never grants verified_complete with zero findings (mirrors the Modelo 200 implies_nonzero worked example). Closes the silent-zero-base deferred rows. Executor: vaultspec-standard-executor.

### Phase `W05.P08` - Applicability and settlement verify gate

Derive prorrata applicability fail-closed-to-visible, emit the per-period missing-carry advisory, add the settlement-period verify ADVISORY finding, and verify-close the silent-zero-base deferred rows.

- [x] `W05.P08.S32` - derive prorrata applicability fail-closed-to-visible: prorrata applies when the register holds an active entry OR the ejercicio shows sin-derecho volumes (declared or ledger-projected); `src/aeat/application/calculations/_prorrata_regularizacion.py`.
- [x] `W05.P08.S33` - emit a per-period calculate advisory naming the missing carry (first ejercicio records the inicio-actividad percentage, otherwise seed or record the prior definitive) whenever prorrata applies and no provisional percentage resolves through the ladder; `src/aeat/application/calculations/_prorrata_regularizacion.py`.
- [x] `W05.P08.S34` - add the settlement-period verify ADVISORY predicate so the gate never grants verified_complete with zero findings on an applies-but-unresolved prorrata, mirroring the Modelo 200 implies_nonzero worked example (no-silent-under-declaration); `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/verification_expectations/`.
- [x] `W05.P08.S35` - add tests proving a mixed trader can no longer silently deduct 100% in-year, silently skip casilla 44, or silently zero the deducible side, while a fully-taxable trader keeps the art-94 full-deduction default untouched; `src/aeat/application/calculations/tests/test_prorrata_regularizacion.py`.
- [x] `W05.P08.S36` - verify-close the silent-zero-base deferred prorrata volume rows (W01.P02.S03/S04 of the silent-zero-base plan) with an exec record referencing this feature's cross-period model as their resolution; `.vault/exec/2026-06-19-silent-zero-base-aggregation/`.

## Wave `W06` - Deferred axes (schema slots from birth) and close review

Record the deferred especial per-input apportionment, the art-103.Dos.2 +10% mandatory-especial comparison, sectores diferenciados per-sector registers, the art-104.Tres special denominator, art-105.Cinco, and automatic art-104.Tres ledger-rollup exclusion classification as honest deferred Steps or noted follow-ups, with the register regime/sector schema slots already present so they land without migration. Close with an independent honesty review. Executors: vaultspec-low-executor (deferred docs), vaultspec-code-reviewer (close review).

### Phase `W06.P09` - Deferred axes and close review

Record the deferred especial / +10% / sectores diferenciados / art-104.Tres / art-105.Cinco axes as honest deferred Steps or follow-ups behind the from-birth schema slots, and run the independent campaign-close honesty review.

- [x] `W06.P09.S37` - record the deferred prorrata especial per-input apportionment and the art-103.Dos.2 +10% mandatory-especial comparison advisory as an honest deferred Step behind the from-birth regime schema slot (needs especial to exist first); `.vault/exec/2026-07-06-cross-period-prorrata/`.
- [x] `W06.P09.S38` - record the deferred sectores diferenciados per-sector registers, the art-104.Tres financial/inmobiliario special denominator, and the art-105.Cinco interrupted-activity three-year rule as noted follow-ups behind the from-birth sector schema slot; `.vault/exec/2026-07-06-cross-period-prorrata/`.
- [x] `W06.P09.S39` - record the deferred automatic art-104.Tres exclusion classification in the ledger rollup as a follow-up (the rollup stays a reconciliation check until it lands); `.vault/exec/2026-07-06-cross-period-prorrata/`.
- [x] `W06.P09.S40` - run the independent campaign-close honesty review (vaultspec-code-reviewer against the ADR, plan, and commit range), persist it as a vault audit, and track every surfaced item as a new Step with a verification gate (aeat-campaign-close-honesty-review); `.vault/audit/2026-07-06-cross-period-prorrata-audit.md`.
- [x] `W06.P09.S41` - record the real-source provisioning blocker for PRORRATA_REGULARIZACION, keep the source deferred, and split the actual promotion into the W07 registry, resolver, enrollment, and close-review work schedule; `.vault/exec/2026-07-06-cross-period-prorrata/2026-07-06-cross-period-prorrata-W06-P09-S41.md; .vault/audit/2026-07-06-cross-period-prorrata-audit.md; .vault/plan/2026-07-06-cross-period-prorrata-plan.md`.

## Wave `W07` - Real source provisioning and promotion

Build the actual registry-declared and resolver-backed PRORRATA_REGULARIZACION source before removing any deferred carve-out: selector contract, binding targets, calculation timing, live mesh enrollment, caller-override disposition, bienes-inversion dependency reconciliation, and close-review gates.

### Phase `W07.P10` - Registry and selector contract

Make prorrata_regularizacion a legal registry-declared source before any mesh promotion: typed selector validation, Modelo 303 casilla 44 binding data, formula implications, and a grounded decision for the claimed Modelo 390 annual target.

- [x] `W07.P10.S42` - add a typed prorrata_regularizacion selector contract and selector-registry construction gate so the source is a legal DataBindingDefinition.source before any TOML binding is declared; `src/aeat/domain/calculations/registry/_bindings.py; src/aeat/domain/calculations/registry/tests/test_selector_shape.py`.
- [x] `W07.P10.S43` - provision the Modelo 303 casilla 44 prorrata_regularizacion binding rows for current registry revisions, convert the target from manual to bound only with legal/source citations and formula-consumption implications proven; `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/; src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/; src/aeat/domain/calculations/registry/tests/`.
- [x] `W07.P10.S44` - ground the Modelo 390 annual regularizacion target, declare its future prorrata_regularizacion binding/export grounding, keep box 522 manual until S45/S46 materialise values, and include 522 in the annual deductible total formula; `src/aeat/_data/registry/aeat/modelos/390/revisions/2010-y-siguientes/; src/aeat/domain/calculations/registry/tests/`.

### Phase `W07.P11` - Resolver timing and value materialisation

Solve the current pre-calculation source-resolution limitation so the live resolver can consume current-year declared/computed prorrata inputs and prior-year/register carry without fabricating values or duplicating formula logic.

- [x] `W07.P11.S45` - design and implement the calculation-order seam that exposes current-year prorrata volume, definitive percentage, and deductible-total values to the prorrata_regularizacion resolver without reimplementing formula business logic; `src/aeat/application/modelo/_calculation_actions.py; src/aeat/domain/calculations/registry/_formula_initial_values.py; src/aeat/application/modelo/tests/`.
- [x] `W07.P11.S46` - implement the prorrata_regularizacion live source resolver with binding values, unresolved diagnostics, and provenance from the register or stamped prior observation plus current-year registry values; `src/aeat/application/calculations/_prorrata_regularizacion.py; src/aeat/application/calculations/__init__.py; src/aeat/application/calculations/tests/`.

### Phase `W07.P12` - Enrollment, dependency reconciliation, and close review

Flip PRORRATA_REGULARIZACION from deferred to enrolled only after the real source path exists, then reconcile the bienes-inversion dependency trigger and run the promotion close-review gates.

- [x] `W07.P12.S47` - enroll PRORRATA_REGULARIZACION in the live application source mesh, caller-override carry disposition, and resolver-enrollment gates, then remove it from DEFERRED_SOURCE_KIND_TARGETS and the deferred undeclared taxonomy carve-out; `src/aeat/application/aggregation/_source_mesh.py; src/aeat/application/modelo/_calculation_actions.py; src/aeat/application/modelo/_calculation_source_policy.py; src/aeat/domain/calculations/registry/tests/test_binding_source_kind_taxonomy.py; src/aeat/application/modelo/tests/test_binding_source_kind_mesh_parity.py; src/aeat/application/aggregation/tests/`.
- [x] `W07.P12.S48` - reconcile the BIENES_INVERSION_REGULARIZACION promotion_depends_on trigger after prorrata_regularizacion lands, either promoting the casilla 43 source or re-ratifying a governed remaining blocker with tests; `src/aeat/application/aggregation/_source_mesh.py; src/aeat/application/calculations/_bienes_inversion_regularizacion.py; src/aeat/application/modelo/_bienes_inversion_advisory.py; src/aeat/application/aggregation/tests/`.
- [x] `W07.P12.S49` - run the W07 promotion close review against the ADR, selector and registry bindings, live resolver, source-kind parity, AEAT manual oracle, M303 advisory behavior, and vault feature/frontmatter gates; `.vault/audit/2026-07-06-cross-period-prorrata-audit.md; .vault/exec/2026-07-06-cross-period-prorrata/; src/aeat/application/calculations/tests/test_prorrata_regularizacion_oracle.py; src/aeat/application/modelo/tests/test_prorrata_regularizacion_advisory.py; src/aeat/application/modelo/tests/test_verification_m303_prorrata_advisory.py`.

## Description

Implements the accepted cross-period-prorrata ADR: the LIVA arts. 102-106
provisional-to-definitive prorrata lifecycle as a tracked, evidence-backed
cross-year computation. The carry home is a per-ejercicio ProrrataRegister (O3),
a profile-scoped encrypted secure-object singleton on the bienes-inversion
register pattern, seeded from the stamped prior settlement observation
(art-105.Uno) and carrying provenance-tagged art-105.Dos/Tres overrides. The
provisional percentage apportions the deducible cuotas in-year inside the one
shared ledger IVA aggregation path (O5, art-104.Uno); the settlement period
computes the definitive percentage from operator-declared annual volumes (O7,
authority unchanged), feeds Modelo 303 casilla 44 and the Modelo 390 annual
field via compute_regularizacion_prorrata_anual, and writes the definitiva back
to seed year+1, with a ledger volume rollup as a non-blocking divergence
advisory only. Applicability is derived fail-closed-to-visible so a mixed trader
can no longer silently deduct 100% in-year, silently skip casilla 44, or
silently zero the deducible side (resolving the silent-zero-base deferred rows).
PRORRATA_REGULARIZACION stays DEFERRED until the chain is proven end to end
against a bundled AEAT Manual practico IVA oracle; especial per-input
apportionment, the +10% comparison, sectores diferenciados, the art-104.Tres
special denominator, and art-105.Cinco are deferred behind the from-birth
regime/sector schema slots.

The compute substrate (domain/iva/_prorrata.py: compute_prorrata_definitiva_anual,
compute_regularizacion_prorrata_anual, the art-106 especial classification) is
stable and is consumed, not re-opened. Net-new surfaces are the domain
prorrata_register package, its persistence adapter, the seed/carry application
layer, the in-year apportionment threading in the shared aggregation path, and
the settlement projection plus source-kind promotion. All grounding is verbatim
against the bundled consolidated LIVA (ley-37-1992.html) per the ADR; no
regulated percentage is ever fabricated. See the ADR and the
silent-zero-base-aggregation plan/audit in `related:` for the authorising chain.

## Steps

## Parallelization

## Verification
