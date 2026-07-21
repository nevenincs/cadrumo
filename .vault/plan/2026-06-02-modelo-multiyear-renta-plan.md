---
tags:
  - '#plan'
  - '#modelo-multiyear-renta'
date: '2026-06-02'
modified: '2026-07-17'
tier: L4
related:
  - '[[2026-06-02-modelo-multiyear-renta-adr]]'
  - '[[2026-06-02-modelo-200-base-determination-adr]]'
  - '[[2026-05-21-work-verify-deadline-independence-adr]]'
  - '[[2026-06-02-modelo-multiyear-renta-353-grupo-aggregation-adr]]'
  - '[[2026-06-02-modelo-720-prior-year-baseline-adr]]'
  - '[[2026-06-02-modelo-multiyear-renta-income-adr]]'
  - '[[2026-06-02-modelo-714-patrimonio-engine-adr]]'
  - '[[2026-06-02-modelo-multiyear-renta-151-beckham-adr]]'
  - '[[2026-05-27-m210-irnr-full-engine-adr]]'
  - '[[2026-06-02-modelo-721-cripto-data-fidelity-adr]]'
  - '[[2026-06-02-modelo-multiyear-renta-151-beckham-research]]'
  - '[[2026-06-02-modelo-multiyear-renta-353-grupo-aggregation-research]]'
  - '[[2026-06-02-modelo-multiyear-renta-income-research]]'
---

# `modelo-multiyear-renta` `multi-year-renta modelo authorization campaign` plan

Enroll all 30 supported modelos into the multi-year-renta authorization gate, each via a real-adapter end-to-end persona test that drives backends across at least two distinct renta years.

## Description

This campaign executes the foundational gate ADR `2026-06-02-modelo-multiyear-renta-adr`: every modelo's calculation backend is non-functional until an authorization gate is lifted, and the gate lifts only when a passing end-to-end persona test, observed by a recorder, drove the real engine and adapters across at least two distinct renta (annual) periods. No modelo is out-of-scope. The plan is L4 because it spans multiple weeks, a multi-agent coding swarm, two or more package boundaries (registry data, core enums, registry authority, application calculations, CLI entrypoints, calculation engines), and an external project-management association.

W01 builds the four-layer gate spine (declarative `authorization.toml` manifest, derived per-revision capability in `core/access_gate`, hard-cut CI meta-test printing authorized N/30, and the advisory `work calculate` banner) plus the dual-mode enrollment recorder in `_multi_year.py`, and authors the mechanism-specific co-backing ADRs the enrollment Waves depend on. W02 through W07 are the enrollment Waves: every Phase is one modelo, sequenced by domain (IRPF income spine, IRPF retenciones-to-resumenes reconciliation, IVA, Impuesto sobre Sociedades, IRNR/wealth/impatriate engine-build, and informativas/censo/IAE). Each modelo's enrollment-evidence class (CALC-CROSS-RENTA, RECONCILIATION-CROSS-RENTA, DATA-FIDELITY-CROSS-RENTA, THRESHOLD/CONTINUITY-CROSS-RENTA, or ENGINE-BUILD-THEN-CALC) is named in its Phase heading and dictates the test shape. Each enrollment spans two full annual cycles using same-revision adjacent years (e.g. 2024 plus 2025) to avoid revision-boundary complexity in the first pass.

The reference E2E pattern is `test_modelo_130_carry_forward_continuity.py`: seed a prior-year observation, open an `isolated_runtime_profile`, calculate via real encrypted SQLite repos and the real registry authority, and assert the cross-renta invariant. The `filing_year_delta` / `max_year_delta` prefill selector machinery already supports cross-year binding (used by 303/390), so the M100/M200/M202 prior-year hooks are registry-authoring tasks plus cap formulas, not new infrastructure. The engine-build modelos (714, 151, 721 with no calculation surface; 210 declared-but-unwired) require their engine before any genuine two-year calculation exists to record; that work is budgeted in W06 behind the A5 ADRs.

The plan is co-backed by the foundational gate ADR, the existing `2026-06-02-modelo-200-base-determination-adr` and `2026-05-21-work-verify-deadline-independence-adr`, and the mechanism-specific ADRs authored in W01.P04 (A2 353-322 aggregation, A3 720 asset baseline, A4 M100/M200/M202 prior-year binding, A5 engine-build for 714/151/210/721). Those W01.P04-authored ADRs are added to this plan's `related:` frontmatter as they land.

## Epic intent

Lift the per-modelo authorization gate for all 30 supported modelos: every modelo enrolls into the multi-year (>=2 distinct renta period) authorization gate via a real-adapter end-to-end persona test that a recorder confirms drove real backends across at least two distinct renta years. No modelo is out-of-scope (owner mandate, non-negotiable). The campaign is tracked under the GitHub project board epic modelo-multiyear-renta-authorization (issue series chore/476-restructure-execution worktree); the milestone reports complete only when the meta-test prints authorized 30/30. Horizon: multi-week, multi-agent, driven by the persistent coding swarm (coder-opus-is on gate infrastructure W01; the enrollment swarm parallelises W02-W07 after W01 lands). Backed by the foundational gate ADR plus the mechanism-specific ADRs authored within this plan (W01 ADR-authoring phase).

## Wave `W01` - Gate infrastructure and mechanism ADRs

Build the four-layer authorization gate spine (declarative manifest, derived per-revision capability, hard-cut CI meta-test, advisory CLI banner) and author the mechanism-specific ADRs the later enrollment Waves depend on. Every enrollment Step in W02-W07 is blocked by this Wave: enrollment writes to the manifest and relies on the dual-mode recorder. Backed by the foundational gate ADR; this Wave also produces the co-backing mechanism ADRs A2 (353<-322 aggregation), A3 (720 prior-year baseline), A4 (M100/M200/M202 prior-year cross-renta binding), and A5 (engine-build ADRs for 714/151/210/721).

### Phase `W01.P01` - Declarative manifest and derived capability

Author the authorization.toml manifest as the sole authorization source of truth, fingerprint it into the registry tree, and derive the per-revision capability StrEnum and record at the registry boundary.

- [x] `W01.P01.S01` - author the directory-mode default-deny authorization manifest fragments with per-modelo renta_years claims, UNAUTHORIZED-by-absence (vaultspec-high-executor); `src/aeat/_data/registry/aeat/authorization.d`.
- [x] `W01.P01.S02` - fingerprint authorization.d manifest fragments into the registry tree fingerprint so cache invalidates on manifest edit (vaultspec-high-executor); `src/aeat/domain/calculations/registry/_loader.py`.
- [x] `W01.P01.S03` - declare the closed authorization-status StrEnum and the per-revision authorization record (vaultspec-high-executor); `src/aeat/core/access_gate/_authorization.py`.
- [x] `W01.P01.S04` - derive the per-modelo authorization capability from the manifest at the registry boundary, never authored independently (vaultspec-high-executor); `src/aeat/domain/calculations/registry/_authority.py`.
- [x] `W01.P01.S05` - write roundtrip tests asserting manifest absence authorizes zero and a listed modelo derives its capability (vaultspec-standard-executor); `src/aeat/core/access_gate/tests/test_authorization_manifest.py`.

### Phase `W01.P02` - Dual-mode enrollment recorder

Build the recorder in _multi_year.py supporting both calculation-based year capture and non-calculation explicit two-year-context registration, with the >=2-distinct-renta-years invariant enforced at the pydantic type boundary. This Phase also closes the cross-cutting coverage gap on MultiYearResolver / resolve_prior_year_observations, which today carries zero direct tests yet a docstring claiming M200/M202, M303 prorrata, M303 regularizacion-inversiones, and annual quarterly roll-up use-cases: each claim gets a real-adapter integration test or the unsubstantiated claim is deleted.

- [x] `W01.P02.S06` - add the dual-mode enrollment recorder with calculation-based and non-calculation two-year-context capture (vaultspec-high-executor); `src/aeat/application/calculations/_multi_year.py`.
- [x] `W01.P02.S07` - enforce the >=2-distinct-renta-years invariant at the pydantic type boundary so a malformed evidence record cannot construct (vaultspec-high-executor); `src/aeat/application/calculations/_multi_year.py; src/aeat/application/calculations/tests/test_multi_year_recorder.py`.
- [x] `W01.P02.S08` - write an anti-tautology test proving a single-year evidence record raises ValidationError (vaultspec-standard-executor); `src/aeat/application/calculations/tests/test_multi_year_recorder.py`.
- [x] `W01.P02.S88` - reconcile the removed MultiYearResolver orphan: confirm no live resolver claim remains, preserve live PreviousFilingSourceResolver and carry-gate coverage, and defer any future multi-year scanner until it has a real caller (vaultspec-high-executor); `src/aeat/application/calculations/_multi_year.py; src/aeat/application/calculations/tests/test_carry_gate_parity.py; .vault/exec/2026-06-26-binding-fold-in-carry-unification/2026-06-26-binding-fold-in-carry-unification-P04-S16.md; .vault/exec/2026-06-26-binding-fold-in-carry-unification/2026-06-26-binding-fold-in-carry-unification-P04-S17.md`.

### Phase `W01.P03` - CI meta-test and advisory CLI surface

Author the hard-cut no-baseline meta-test that prints authorized N/30 and cross-checks recorded year-sets against the manifest, and add the advisory work calculate banner for unauthorized-but-has-engine modelos while preserving the work create stub refusal.

- [x] `W01.P03.S09` - maintain the hard-cut no-baseline authorization meta-test over the live canonical fleet, printing authorized N/FLEET_SIZE with the UNAUTHORIZED id list (vaultspec-high-executor); `src/aeat/tests/test_modelo_authorization_gate.py`.
- [x] `W01.P03.S10` - cross-check each recorded year-set equals the manifest renta_years claim, contains >=2 distinct years, and calls the enrollment contract (vaultspec-high-executor); `src/aeat/tests/test_modelo_authorization_gate.py`.
- [x] `W01.P03.S11` - add the ADVISORY work-calculate banner naming the unauthorized state for unauthorized-but-has-engine modelos (vaultspec-standard-executor); `src/aeat/entrypoints/cli/_modelo_work_calculate_cli.py; src/aeat/entrypoints/cli/tests/test_modelo_authorization_advisory_banner.py`.
- [x] `W01.P03.S12` - assert the current guard_unsupported_work_modelo hard refusal at work create still fires for no-engine and unsupported stubs (vaultspec-code-reviewer); `src/aeat/application/modelo/_work_create_policy.py; src/aeat/entrypoints/cli/tests/test_modelo_unsupported_work_refusal.py; src/aeat/entrypoints/cli/tests/test_root_fallback_write_guard.py`.

### Phase `W01.P04` - Mechanism-specific backing ADRs

Author the co-backing mechanism ADRs the enrollment Waves depend on: A2 353<-322 aggregation, A3 720 prior-year baseline, A4 M100/M200/M202 prior-year cross-renta binding, and the A5 engine-build ADRs for 714/151/210/721.

- [x] `W01.P04.S13` - author the A2 ADR for the 353<-322 monthly grupo-entidades aggregation mechanism grounded in LIVA art.163 (vaultspec-high-executor); `.vault/adr/2026-06-02-modelo-multiyear-renta-353-grupo-aggregation-adr.md`.
- [x] `W01.P04.S14` - author the A3 ADR for the 720 prior-year asset-baseline previous_filing binding and re-declaration trigger grounded in RD 1065/2007 (vaultspec-high-executor); `.vault/adr/2026-06-02-modelo-720-prior-year-baseline-adr.md`.
- [x] `W01.P04.S15` - author the A4-M100 income-tax prior-year cross-renta binding ADR covering M100 saldos and deducciones pendientes (vaultspec-high-executor); `.vault/adr/2026-06-02-modelo-multiyear-renta-income-adr.md`.
- [x] `W01.P04.S16` - author the A4-M200 income-tax prior-year cross-renta binding ADR covering BIN compensation and cap mechanics (vaultspec-high-executor); `.vault/adr/2026-06-02-modelo-multiyear-renta-income-adr.md`.
- [x] `W01.P04.S17` - author the A4-M202 income-tax prior-year cross-renta binding ADR covering modalidad 40.2 prior-cuota base (vaultspec-high-executor); `.vault/adr/2026-06-02-modelo-multiyear-renta-income-adr.md`.
- [x] `W01.P04.S18` - author the A5-714 engine-build ADR for Patrimonio wealth base and limite conjunto sequencing grounded in Ley 19/1991 (vaultspec-high-executor); `.vault/adr/2026-06-02-modelo-714-patrimonio-engine-adr.md`.
- [x] `W01.P04.S19` - author the A5-151 engine-build ADR for the Beckham flat-rate regime and six-year window grounded in Ley 35/2006 art.93 (vaultspec-high-executor); `.vault/adr/2026-06-02-modelo-multiyear-renta-151-beckham-adr.md`.
- [x] `W01.P04.S20` - author the A5-210 engine-wiring ADR for the IRNR calculation surface grounded in TRLIRNR RDLeg 5/2004 (vaultspec-high-executor); `.vault/adr/2026-05-27-m210-irnr-full-engine-adr.md`.
- [x] `W01.P04.S21` - author the A5-721 data-fidelity and obligation-trigger ADR grounded in Ley 58/2003 DA18 and Orden HFP/886/2023 (vaultspec-high-executor); `.vault/adr/2026-06-02-modelo-721-cripto-data-fidelity-adr.md`.

## Wave `W02` - IRPF income spine

Enroll the IRPF income-tax calculation modelos 130, 100, and 131 into the gate via real-adapter >=2-renta E2E persona tests. Depends on W01 (gate + recorder + M100/M131 prior-year binding from A4). M130 extends the existing carry-forward continuity reference into a second renta year; M100 and M131 add prior-year cross-renta hooks. Reuses the M303 iva_wallet pattern: seed prior-year observation, isolated_runtime_profile, calculate, assert source_filing_year.

### Phase `W02.P05` - Modelo 130 (IRPF pago fraccionado, CALC-CROSS-RENTA)

Extend the existing M130 carry-forward continuity reference into a second renta year so the recorder captures two distinct filing_years for the autonomo estimacion directa pago-fraccionado.

- [x] `W02.P05.S22` - reconcile the M130 multi-year enrollment test that drives two renta years through real adapters and records the manifest-matched filing_year set; `src/aeat/application/calculations/tests/test_modelo_130_multiyear_renta_enrollment.py`.
- [x] `W02.P05.S23` - reconcile the M130 authorization manifest entry with renta_years matching the recorded year-set; `src/aeat/_data/registry/aeat/authorization.d/130.toml`.

### Phase `W02.P06` - Modelo 100 (IRPF declaracion anual, CALC-CROSS-RENTA)

Enroll the annual Renta with a prior-year cross-renta hook (saldos/deducciones pendientes, filing_year_delta=-1) per A4; capital-loss 4yr carry under Ley 35/2006 art.49.

- [x] `W02.P06.S24` - reconcile the M100 general-base negative carry prior-year binding from previous_filing casilla 1391 into current-year casilla 1388 per A4-M100; `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/bindings/0020-renta-2024-base-liquidable-negativa-anterior.toml; src/aeat/_data/registry/aeat/modelos/100/revisions/2025/bindings/0048-renta-2025-base-liquidable-negativa-anterior.toml; src/aeat/_data/registry/aeat/modelos/100/revisions/2024/casillas/1332-1388.toml; src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/1387-1388.toml`.
- [x] `W02.P06.S25` - reconcile the M100 two-renta enrollment test proving the general-base negative saldo wiring through real calculate and manifest evidence; `src/aeat/application/calculations/tests/test_modelo_100_multiyear_renta_enrollment.py`.
- [x] `W02.P06.S26` - reconcile the M100 authorization manifest entry with renta_years matching the recorded year-set; `src/aeat/_data/registry/aeat/authorization.d/100.toml`.

### Phase `W02.P07` - Modelo 131 (IRPF estimacion objetiva, CALC-CROSS-RENTA)

Enroll the modulos pago fraccionado across two renta years for the estimacion objetiva autonomo, asserting the rendimiento de modulos cross-year carry.

- [x] `W02.P07.S27` - reconcile the M131 modules continuity enrollment test across two renta years via real adapters and manifest evidence; `src/aeat/application/calculations/tests/test_modelo_131_carry_forward_continuity.py`.
- [x] `W02.P07.S28` - reconcile the M131 authorization manifest entry with renta_years matching the recorded year-set; `src/aeat/_data/registry/aeat/authorization.d/131.toml`.

## Wave `W03` - IRPF retenciones to annual resumenes reconciliation

Enroll the quarterly-to-annual reconciliation chains 111->190, 115->180, 123->193 via RECONCILIATION-CROSS-RENTA E2E tests spanning two renta years. Depends on W01. Each test drives the periodic feeder filings and the annual resumen for two adjacent same-revision years and reconciles the withheld totals across both years.

### Phase `W03.P08` - Modelo 190 reconciled from Modelo 111 (RECONCILIATION-CROSS-RENTA)

Enroll the 111->190 chain: quarterly (1T-4T) retenciones del trabajo feeders reconciled against the annual resumen 190 across two renta years.

- [x] `W03.P08.S29` - reconcile the 111->190 two-renta reconciliation enrollment test using real withholding feeder observations and annual manifest evidence; `src/aeat/application/calculations/tests/test_modelo_190_111_reconciliation_continuity.py`.
- [x] `W03.P08.S30` - reconcile the M190 authorization manifest entry with renta_years matching the recorded year-set; `src/aeat/_data/registry/aeat/authorization.d/190.toml`.

### Phase `W03.P09` - Modelo 180 reconciled from Modelo 115 (RECONCILIATION-CROSS-RENTA)

Enroll the 115->180 chain: quarterly retenciones sobre arrendamientos feeders reconciled against the annual resumen 180 across two renta years.

- [x] `W03.P09.S31` - reconcile the 115->180 two-renta reconciliation enrollment test using real arrendamiento feeder observations and annual manifest evidence; `src/aeat/application/calculations/tests/test_modelo_180_115_reconciliation_continuity.py`.
- [x] `W03.P09.S32` - reconcile the M180 authorization manifest entry with renta_years matching the recorded year-set; `src/aeat/_data/registry/aeat/authorization.d/180.toml`.

### Phase `W03.P10` - Modelo 193 reconciled from Modelo 123 (RECONCILIATION-CROSS-RENTA)

Enroll the 123->193 chain: retenciones sobre capital mobiliario feeders reconciled against the annual resumen 193 across two renta years.

- [x] `W03.P10.S33` - reconcile the 123->193 two-renta reconciliation enrollment test using real capital-mobiliario feeder observations and annual manifest evidence; `src/aeat/application/calculations/tests/test_modelo_193_123_reconciliation_continuity.py`.
- [x] `W03.P10.S34` - reconcile the M193 authorization manifest entry with renta_years matching the recorded year-set; `src/aeat/_data/registry/aeat/authorization.d/193.toml`.

## Wave `W04` - IVA modelos

Enroll the IVA fleet 303, 390, 322, 353, 369, 349, 308, 309, 360 into the gate. Depends on W01 and, for 353, on the A2 aggregation ADR. 303 and 390 are CALC/RECONCILIATION quick-wins extending the existing binding-prefill pattern across two renta years; 322/353 are grupo-entidades CALC-CROSS-RENTA; 369/349/308/309/360 are DATA-FIDELITY-CROSS-RENTA informativas.

### Phase `W04.P11` - Modelo 303 (IVA autoliquidacion, CALC-CROSS-RENTA)

Enroll the IVA autoliquidacion: 4T/N -> 1T/N+1 cuota-a-compensar carry across two renta years via the iva_wallet engine integration pattern.

- [x] `W04.P11.S35` - reconcile the M303 two-renta compensation-carry enrollment test proving 4T/2025 saldo into 1T/2026 casilla 110 via real registry calculation and relation resolver; `src/aeat/application/calculations/tests/test_modelo_303_compensacion_carry_forward_continuity.py; src/aeat/_data/registry/aeat/modelos/303/revisions/2024-y-siguientes/relations/0001-relations.toml`.
- [x] `W04.P11.S36` - reconcile the M303 authorization manifest entry with renta_years matching the recorded year-set; `src/aeat/_data/registry/aeat/authorization.d/303.toml`.

### Phase `W04.P12` - Modelo 390 (IVA resumen anual, RECONCILIATION-CROSS-RENTA)

Enroll the IVA annual resumen reconciled against its four 303 feeders across two renta years, extending the existing binding-prefill pattern.

- [x] `W04.P12.S37` - reconcile the M390 two-renta annual reconciliation test against four M303 quarterly feeders; `src/aeat/application/calculations/tests/test_modelo_390_303_reconciliation_continuity.py; src/aeat/_data/registry/aeat/modelos/390/revisions/2022-y-siguientes/bindings/0001-bindings.toml`.
- [x] `W04.P12.S38` - reconcile the M390 authorization manifest entry with renta_years matching the recorded year-set; `src/aeat/_data/registry/aeat/authorization.d/390.toml`.

### Phase `W04.P13` - Modelo 322 (IVA grupo entidades individual, CALC-CROSS-RENTA)

Enroll the grupo-entidades individual autoliquidacion across two renta years; feeds the 353 aggregation per A2 (LIVA art.163).

- [x] `W04.P13.S39` - reconcile the M322 two-renta REGE individual calculation enrollment test for December 2025 and 2026; `src/aeat/application/calculations/tests/test_modelo_322_grupo_individual_continuity.py`.
- [x] `W04.P13.S40` - reconcile the M322 authorization manifest entry with renta_years matching the recorded year-set; `src/aeat/_data/registry/aeat/authorization.d/322.toml`.

### Phase `W04.P14` - Modelo 353 (IVA grupo entidades agregado, CALC-CROSS-RENTA)

Enroll the grupo-entidades aggregated autoliquidacion via the A2 353<-322 monthly aggregation mechanism across two renta years.

- [x] `W04.P14.S41` - reconcile the 353<-322 per-member aggregation bindings using per_grupo_member grouping and sum aggregation; `src/aeat/_data/registry/aeat/modelos/353/revisions/2008-y-siguientes/bindings/0002-bindings.toml`.
- [x] `W04.P14.S42` - reconcile the M353 two-renta aggregation enrollment test summing two members real 322 calculations into 353; `src/aeat/application/calculations/tests/test_modelo_353_grupo_aggregation_continuity.py`.
- [x] `W04.P14.S43` - reconcile the M353 authorization manifest entry with renta_years matching the recorded year-set; `src/aeat/_data/registry/aeat/authorization.d/353.toml`.

### Phase `W04.P15` - Modelo 369 (IVA OSS/IOSS, DATA-FIDELITY-CROSS-RENTA)

Enroll the One-Stop-Shop declaration via year-over-year data-fidelity and provenance roundtrip across two renta years (no numeric oracle).

- [x] `W04.P15.S44` - reconcile the M369 calculation-mode OSS Union-scheme cuota-total enrollment test across two renta years; `src/aeat/application/calculations/tests/test_modelo_369_oss_fidelity.py`.
- [x] `W04.P15.S45` - reconcile the M369 authorization manifest entry with calculation evidence_class and renta_years matching the recorded year-set; `src/aeat/_data/registry/aeat/authorization.d/369.toml`.

### Phase `W04.P16` - Modelo 349 (IVA operaciones intracomunitarias, DATA-FIDELITY-CROSS-RENTA)

Enroll the recapitulativa de operaciones intracomunitarias via year-over-year data-fidelity and provenance roundtrip across two renta years.

- [x] `W04.P16.S46` - reconcile the M349 intracomunitario data-fidelity enrollment test proving encrypted observation roundtrip and year isolation; `src/aeat/application/calculations/tests/test_modelo_349_intracomunitario_fidelity.py`.
- [x] `W04.P16.S47` - reconcile the M349 authorization manifest entry with renta_years matching the recorded year-set; `src/aeat/_data/registry/aeat/authorization.d/349.toml`.

### Phase `W04.P17` - Modelo 308 (IVA solicitud devolucion, DATA-FIDELITY-CROSS-RENTA)

Enroll the devolucion-a-no-establecidos / recargo-equivalencia request via year-over-year data-fidelity and provenance roundtrip across two renta years.

- [x] `W04.P17.S48` - reconcile the M308 ad-hoc data-fidelity enrollment test proving two-renta encrypted observation roundtrip; `src/aeat/application/calculations/tests/test_modelo_308_adhoc_fidelity.py`.
- [x] `W04.P17.S49` - reconcile the M308 authorization manifest entry with renta_years matching the recorded year-set; `src/aeat/_data/registry/aeat/authorization.d/308.toml`.

### Phase `W04.P18` - Modelo 309 (IVA no periodica, DATA-FIDELITY-CROSS-RENTA)

Enroll the declaracion-liquidacion no periodica via year-over-year data-fidelity and provenance roundtrip across two renta years.

- [x] `W04.P18.S50` - reconcile the M309 calculation-mode ad-hoc cuota-total enrollment test across two renta years; `src/aeat/application/calculations/tests/test_modelo_309_adhoc_fidelity.py`.
- [x] `W04.P18.S51` - reconcile the M309 authorization manifest entry with calculation evidence_class and renta_years matching the recorded year-set; `src/aeat/_data/registry/aeat/authorization.d/309.toml`.

### Phase `W04.P19` - Modelo 360 (IVA devolucion otros estados, DATA-FIDELITY-CROSS-RENTA)

Enroll the devolucion-a-empresarios-en-otros-estados request via year-over-year data-fidelity and provenance roundtrip across two renta years.

- [x] `W04.P19.S52` - reconcile the M360 ad-hoc refund-request data-fidelity enrollment test proving two-renta roundtrip and estado-miembro isolation; `src/aeat/application/calculations/tests/test_modelo_360_adhoc_fidelity.py`.
- [x] `W04.P19.S53` - reconcile the M360 authorization manifest entry with renta_years matching the recorded year-set; `src/aeat/_data/registry/aeat/authorization.d/360.toml`.

## Wave `W05` - Impuesto sobre Sociedades

Enroll the IS modelos 200, 202, 232 into the gate. Depends on W01 and on the A4 prior-year-hook ADR for 200 (BIN compensation + 70%/1M cap) and 202 (modalidad 40.2 prior-cuota base). 200 is co-backed by the existing base-determination ADR; 232 is DATA-FIDELITY-CROSS-RENTA (operaciones vinculadas year-over-year fidelity).

### Phase `W05.P20` - Modelo 200 (IS declaracion anual, CALC-CROSS-RENTA)

Enroll the IS annual declaration with the A4 prior-year BIN-compensation hook (70%/1M cap, Ley 27/2014 art.26) across two renta years; co-backed by the base-determination ADR.

- [x] `W05.P20.S54` - reconcile the M200 BIN stock carry binding copying prior pending BIN into the current-year binding surface; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records/relations.toml`.
- [x] `W05.P20.S55` - reconcile the M200 two-renta BIN stock enrollment test and separate 70 percent / 1M cap guard coverage; `src/aeat/application/calculations/tests/test_modelo_200_bin_carry_forward_continuity.py`.
- [x] `W05.P20.S56` - reconcile the M200 authorization manifest entry with renta_years matching the recorded year-set; `src/aeat/_data/registry/aeat/authorization.d/200.toml`.

### Phase `W05.P21` - Modelo 202 (IS pago fraccionado, CALC-CROSS-RENTA)

Enroll the IS pago fraccionado modalidad 40.2 with the A4 prior-cuota-base hook (art.40.2) across two renta years.

- [x] `W05.P21.S57` - reconcile the M202 cuota-base ejercicio anterior bindings from prior Modelo 200 cuota liquida for 2P and 3P; `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/bindings/0003-modelo-202-2025-y-siguientes-cuota-base-ejercicio-anterior.toml; src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/relations/0004-modelo-202-2025-y-siguientes-rel-cuota-base-2p-3p.toml`.
- [x] `W05.P21.S58` - reconcile the M202 2P two-renta enrollment test proving prior M200 cuota liquida feeds current pago fraccionado base; `src/aeat/application/calculations/tests/test_modelo_202_cuota_base_ejercicio_anterior_continuity.py`.
- [x] `W05.P21.S59` - reconcile the M202 authorization manifest entry with renta_years matching the recorded year-set; `src/aeat/_data/registry/aeat/authorization.d/202.toml`.

### Phase `W05.P22` - Modelo 232 (IS operaciones vinculadas, DATA-FIDELITY-CROSS-RENTA)

Enroll the operaciones-vinculadas-y-paraisos informativa via year-over-year data-fidelity and provenance roundtrip across two renta years.

- [x] `W05.P22.S60` - reconcile the M232 related-party data-fidelity enrollment test proving NIF continuity, distinct importes, and threshold coverage; `src/aeat/application/calculations/tests/test_modelo_232_operaciones_vinculadas_fidelity.py`.
- [x] `W05.P22.S61` - reconcile the M232 authorization manifest entry with renta_years matching the recorded year-set; `src/aeat/_data/registry/aeat/authorization.d/232.toml`.

## Wave `W06` - IRNR, wealth, and impatriate engine-build

Build the missing calculation engines for 714 (Patrimonio), 151 (Beckham flat-rate), 721 (crypto obligation-trigger), and complete the declared-but-unwired 210 (IRNR) calculation link, then enroll each via a real two-year calculation. Depends on W01 and on the A5 engine-build ADRs (one per modelo). These modelos cannot be authorized by a test-only change; the engine work is budgeted here before the E2E enrollment.

### Phase `W06.P23` - Modelo 210 (IRNR, ENGINE-BUILD-THEN-CALC)

Complete the declared-but-unwired modelo-210-2025-calculation link, then enroll IRNR via two consecutive annual rental-income groupings (weak cross-renta) per A5; TRLIRNR RDLeg 5/2004.

- [x] `W06.P23.S62` - complete the declared-but-unwired modelo-210-2025-calculation engine link so a real IRNR calculation runs per A5-210 (TRLIRNR RDLeg 5/2004) (vaultspec-high-executor); `src/aeat/domain/calculations/engines/_modelo_210.py`.
- [x] `W06.P23.S63` - write the M210 >=2-renta E2E test using two consecutive annual rental-income groupings via real adapters (vaultspec-high-executor); `src/aeat/application/calculations/test_modelo_210_annual_continuity.py`.
- [x] `W06.P23.S64` - enroll M210 in the authorization manifest with renta_years claim matching the recorded year-set (vaultspec-code-reviewer); `src/aeat/_data/registry/aeat/authorization.toml`.

### Phase `W06.P24` - Modelo 714 (Patrimonio, ENGINE-BUILD-THEN-CALC)

Build the Patrimonio wealth-base engine (60% limite conjunto x-ref to M100) per A5, then enroll a year-over-year wealth-base calculation across two renta years; Ley 19/1991.

- [x] `W06.P24.S65` - build the Patrimonio wealth-base engine with the 60% limite conjunto x-ref to M100 per A5-714 (Ley 19/1991) (vaultspec-high-executor); `src/aeat/domain/calculations/engines/_modelo_714.py`.
- [x] `W06.P24.S66` - declare the modelo-714 calculation application-link surface in the registry (vaultspec-high-executor); `src/aeat/_data/registry/aeat/modelos/714/`.
- [x] `W06.P24.S67` - write the M714 >=2-renta E2E test asserting year-over-year wealth-base calculation via real adapters (vaultspec-high-executor); `src/aeat/application/calculations/test_modelo_714_wealth_continuity.py`.
- [x] `W06.P24.S68` - enroll M714 in the authorization manifest with renta_years claim matching the recorded year-set (vaultspec-code-reviewer); `src/aeat/_data/registry/aeat/authorization.toml`.

### Phase `W06.P25` - Modelo 721 (crypto declaracion, THRESHOLD/CONTINUITY-CROSS-RENTA)

Enroll Modelo 721 as the accepted 720-twin informativa threshold-continuity path: legal-registry correction, threshold parameters, two-year repository/advisory evidence, and no calculation engine or calculation application-link surface.

- [x] `W06.P25.S69` - reconcile Modelo 721 against the accepted no-calculation threshold-continuity ADR and retire the stale crypto engine requirement; `.vault/adr/2026-06-02-modelo-721-cripto-data-fidelity-adr.md`.
- [x] `W06.P25.S70` - assert the Modelo 721 registry keeps threshold parameters and filing/extractor/verification/deadline links without a calculation application-link surface; `src/aeat/_data/registry/aeat/modelos/721/`.
- [x] `W06.P25.S71` - write the M721 >=2-renta threshold-continuity E2E test across 2023 and 2024 via real repository/advisory evidence; `src/aeat/application/calculations/tests/test_modelo_721_cripto_extranjero_fidelity.py`.
- [x] `W06.P25.S72` - enroll M721 in the authorization manifest with renta_years claim matching the recorded year-set (vaultspec-code-reviewer); `src/aeat/_data/registry/aeat/authorization.toml`.

### Phase `W06.P26` - Modelo 151 (IRPF regimen impatriados, ENGINE-BUILD-THEN-CALC)

Build the Beckham flat-rate engine per A5 (Ley 35/2006 art.93), then enroll the flat-rate calculation across two renta years.

- [x] `W06.P26.S73` - build the Beckham flat-rate impatriate engine per A5-151 (Ley 35/2006 art.93) (vaultspec-high-executor); `src/aeat/domain/calculations/engines/_modelo_151.py`.
- [x] `W06.P26.S74` - declare the modelo-151 calculation application-link surface in the registry (vaultspec-high-executor); `src/aeat/_data/registry/aeat/modelos/151/`.
- [x] `W06.P26.S75` - write the M151 >=2-renta E2E test asserting the flat-rate calculation across two renta years via real adapters (vaultspec-high-executor); `src/aeat/application/calculations/test_modelo_151_flat_rate_continuity.py`.
- [x] `W06.P26.S76` - enroll M151 in the authorization manifest with renta_years claim matching the recorded year-set (vaultspec-code-reviewer); `src/aeat/_data/registry/aeat/authorization.toml`.

## Wave `W07` - Informativas, censo, and IAE

Enroll the remaining informativa/structural modelos 347, 184, 720, 036, 840 into the gate. Depends on W01 and, for 720, on the A3 prior-year asset-baseline ADR. 347/184 are DATA-FIDELITY-CROSS-RENTA; 720 is THRESHOLD/CONTINUITY with the +20k prior-year baseline; 036 is obligation-set continuity (alta year N / modificacion year N+1); 840 is the 1M-per-year IAE exemption across two annual contexts.

### Phase `W07.P27` - Modelo 347 (operaciones con terceros, DATA-FIDELITY-CROSS-RENTA)

Enroll the declaracion anual de operaciones con terceras personas via year-over-year data-fidelity and provenance roundtrip across two renta years.

- [x] `W07.P27.S77` - write the M347 data-fidelity E2E test asserting year-over-year fidelity and provenance roundtrip of operaciones-con-terceros across two renta years via real adapters (vaultspec-standard-executor); `src/aeat/application/calculations/test_modelo_347_fidelity_continuity.py`.
- [x] `W07.P27.S78` - enroll M347 in the authorization manifest with renta_years claim matching the recorded year-set (vaultspec-code-reviewer); `src/aeat/_data/registry/aeat/authorization.toml`.

### Phase `W07.P28` - Modelo 184 (atribucion de rentas, DATA-FIDELITY-CROSS-RENTA)

Enroll the entidades-en-atribucion-de-rentas informativa across two renta years; build RegistryModeloObservation member rows directly (operator-keyed, no source adapter).

- [x] `W07.P28.S79` - write the M184 data-fidelity E2E test building atribucion-de-rentas member RegistryModeloObservation rows directly and asserting year-over-year fidelity across two renta years (vaultspec-standard-executor); `src/aeat/application/calculations/test_modelo_184_fidelity_continuity.py`.
- [x] `W07.P28.S80` - enroll M184 in the authorization manifest with renta_years claim matching the recorded year-set (vaultspec-code-reviewer); `src/aeat/_data/registry/aeat/authorization.toml`.

### Phase `W07.P29` - Modelo 720 (bienes en el extranjero, THRESHOLD/CONTINUITY-CROSS-RENTA)

Enroll the declaracion de bienes en el extranjero via the A3 prior-year asset-baseline binding (+20k/50k re-declaration, RD 1065/2007 art.42-bis) across two renta years; export golden-SHA deferred.

- [x] `W07.P29.S81` - author the M720 prior-year asset-baseline previous_filing binding (+20k/50k re-declaration) in the registry per A3 (RD 1065/2007 art.42-bis) (vaultspec-high-executor); `src/aeat/_data/registry/aeat/modelos/720/`.
- [x] `W07.P29.S82` - write the M720 threshold-continuity E2E test asserting the prior-year asset baseline drives the re-declaration obligation across two renta years via real adapters (vaultspec-high-executor); `src/aeat/application/calculations/test_modelo_720_baseline_continuity.py`.
- [x] `W07.P29.S83` - enroll M720 in the authorization manifest with renta_years claim matching the recorded year-set (vaultspec-code-reviewer); `src/aeat/_data/registry/aeat/authorization.toml`.

### Phase `W07.P30` - Modelo 036 (censo, THRESHOLD/CONTINUITY-CROSS-RENTA)

Enroll the declaracion censal via obligation-set continuity across two annual contexts (alta year N / modificacion year N+1), not a numeric carry.

- [x] `W07.P30.S84` - write the M036 obligation-continuity E2E test asserting the censo obligation-set carries across alta year N and modificacion year N+1 via real adapters (vaultspec-standard-executor); `src/aeat/application/calculations/test_modelo_036_obligation_continuity.py`.
- [x] `W07.P30.S85` - enroll M036 in the authorization manifest with renta_years claim matching the recorded year-set (vaultspec-code-reviewer); `src/aeat/_data/registry/aeat/authorization.toml`.

### Phase `W07.P31` - Modelo 840 (IAE, THRESHOLD/CONTINUITY-CROSS-RENTA)

Enroll the Impuesto sobre Actividades Economicas via the 1M-per-year cifra-de-negocios exemption logic across two annual contexts.

- [x] `W07.P31.S86` - write the M840 threshold-continuity E2E test asserting the 1M-per-year cifra-de-negocios exemption across two annual contexts via real adapters (vaultspec-standard-executor); `src/aeat/application/calculations/test_modelo_840_exemption_continuity.py`.
- [x] `W07.P31.S87` - enroll M840 in the authorization manifest with renta_years claim matching the recorded year-set (vaultspec-code-reviewer); `src/aeat/_data/registry/aeat/authorization.toml`.

### Phase `W07.P32` - Residual ADR hardening

Track explicit follow-up work discovered during enrollment closeout where the live green path does not yet discharge a narrower ADR mechanism.

- [x] `W07.P32.S89` - investigate and implement or explicitly supersede the Modelo 721 per-custodian prior-year baseline binding promised by the accepted ADR; `src/aeat/domain/calculations/registry/_bindings_previous_filing.py, src/aeat/domain/calculations/registry/tests/test_modelo_721_registry.py, src/aeat/application/calculations/tests/test_modelo_721_cripto_extranjero_fidelity.py, .vault/adr/2026-06-02-modelo-721-cripto-data-fidelity-adr.md`.

## Parallelization

Waves are sequenced by default. W01 must land and be reviewed before any enrollment Wave begins: enrollment writes to the `authorization.toml` manifest and depends on the dual-mode recorder and the meta-test cross-check. Within W01, P01 (manifest plus derived capability) gates P02 (recorder) and P03 (meta-test plus CLI banner); P04 (mechanism ADRs) runs concurrently with P01-P03 because authoring ADRs touches no production code.

After W01 lands, W02 through W07 parallelise across the coding swarm because no enrollment Wave depends on another. Within each enrollment Wave the per-modelo Phases are independent and parallelise freely, with these hard intra-Wave orderings: each modelo's E2E-test Step precedes its manifest-enrollment Step (you cannot enroll before the recorder has observed the years); each registry-binding Step (M100, M200, M202, M353, M720) precedes that modelo's E2E Step; and each engine-build Step (M210 wiring, M714, M151) precedes its registry-link-declaration Step, which precedes the E2E Step. Modelo 721 follows the accepted no-calculation threshold-continuity path; its unresolved per-custodian prior-year binding mechanism is tracked separately as residual ADR hardening in W07.P32.S89.

Cross-Wave ADR dependencies: M353 (W04.P14) is blocked by the A2 ADR (W01.P04.S13); M720 (W07.P29) by the A3 ADR (S14); M100 (W02.P06) by the A4-M100 ADR (S15), M200 (W05.P20) by A4-M200 (S16), M202 (W05.P21) by A4-M202 (S17); M714 (W06.P24) by the A5-714 ADR (S18), M151 (W06.P26) by A5-151 (S19), M210 (W06.P23) by A5-210 (S20), M721 (W06.P25) by A5-721 (S21). The quick-win order for the first enrollment pass that validates the gate end-to-end is M130, M303, M390 (existing scaffolding plus the established binding-prefill pattern), then the remaining quick-wins M202, M200, M131, M190, M193, M100, M180.

## Verification

The campaign is complete when every Step in every Wave is closed and the following criteria all hold:

- The `test_modelo_authorization_gate.py` meta-test prints `authorized 30/30` with an empty UNAUTHORIZED id list, and is hard-cut with no stored baseline so coverage can only ratchet upward.
- For every one of the 30 modelos, the meta-test confirms the recorded year-set equals the manifest `renta_years` claim and contains at least two distinct renta years; a stub or single-period test reds the gate.
- The `>=2 distinct renta years` invariant is enforced at the pydantic type boundary, proven by the anti-tautology test (S08) that a single-year evidence record raises `ValidationError`.
- Every docstring-claimed `MultiYearResolver.resolve()` use-case has a real-adapter integration test (S88), or the unsubstantiated claim has been deleted from `_multi_year.py`; the M303 (S35) and M200 (S55) enrollment tests exercise the resolver path for their respective claimed use-case so no claim survives unverified.
- Every enrollment E2E test drives real adapters (real encrypted SQLite repos and the real registry authority) across two distinct `filing_year` values, with no mocks, stubs, skips, or xfail, per the roundtrip and quality-gate disciplines. Mechanisms that declare `previous_filing` bindings also exercise the real `previous_filing` resolver.
- Calculation-class assertions are grounded against external authority (AEAT workbooks, BOE or AEAT worked examples, registry-authoritative fixtures, or live oracle replay), never hand-computed from the registry formula under test; data-fidelity and threshold/continuity classes assert provenance, year-over-year fidelity, and obligation logic where no numeric oracle exists.
- The advisory `work calculate` banner names the unauthorized state for unauthorized-but-has-engine modelos without refusing computation, and the existing `_guard_stub_modelo` hard refusal at `work create` still fires for no-engine stubs (S11, S12).
- The `authorization.toml` manifest is fingerprinted into the registry tree fingerprint so a manifest edit invalidates the cache (S02); no path-only cache serves stale authorization.
- Each enrolled modelo carries a `vaultspec-code-review` pass, and the declared project-management association reports the Epic complete.
