---
tags:
  - '#plan'
  - '#cross-period-filing-clean-state'
date: '2026-06-05'
modified: '2026-06-05'
tier: L3
related:
  - '[[2026-06-05-cross-period-filing-clean-state-adr]]'
  - '[[2026-06-05-cross-period-filing-clean-state-research]]'
  - '[[2026-06-05-cross-period-filing-clean-state-reference]]'
  - '[[2026-06-05-cross-period-calculation-guards-research]]'
  - '[[2026-06-05-cross-period-calculation-guards-reference]]'
---


<!-- RETIRED: S03, S04, S05, S07, S09, S10, S11, S12, S13, S14, S15, S16, S17, S18, S19, S20 -->

# `cross-period-filing-clean-state` implementation plan

## Wave `W01` - foundational clean-state guard

This Wave records the completed foundation: typed clean-state proof, calculation exports, workflow enforcement, export enforcement, and focused real-behavior tests for the first cross-period filing-grade guard.

### Phase `W01.P01` - define dependency proof contract

Define the application-level proof model and repository joins that classify cross-period dependencies as clean or blocking.


Implement a uniform clean-state proof for filing-grade cross-period modelo dependencies.

- [x] `W01.P01.S01` - Add clean-state proof model and resolver service; `src/aeat/application/calculations/_cross_period_clean_state.py`.
- [x] `W01.P01.S02` - Expose clean-state proof interfaces through calculation exports; `src/aeat/application/calculations/__init__.py`.

### Phase `W01.P04` - wire filing-grade enforcement

Wire the clean-state proof into calculation, verification, export, and filing boundaries without weakening permissive preview behavior.

- [x] `W01.P04.S06` - Wire clean-state blocking into modelo verification and filing; `src/aeat/application/modelo/_actions.py`.
- [x] `W01.P04.S08` - Gate export on clean-state dependency proof; `src/aeat/application/modelo/_export.py`.

### Phase `W01.P02` - cover state matrix with real tests

Add real-behavior tests for complete, missing, stale, superseded, local-only, AEAT-attested, divergent, and group-incomplete dependency states.

- [x] `W01.P02.S21` - Cover clean-state proof with real repository tests; `src/aeat/application/calculations/tests/test_cross_period_clean_state.py`.
- [x] `W01.P02.S22` - Cover filing-grade gates with real workflow tests; `src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py`.

### Phase `W01.P03` - run focused quality gates

Run focused validation for the changed application, domain, and test surfaces and record any remaining risk.

- [x] `W01.P03.S23` - Run calculation proof tests; `src/aeat/application/calculations/tests`.
- [x] `W01.P03.S24` - Run modelo workflow gate tests; `src/aeat/application/modelo/tests`.
- [x] `W01.P03.S25` - Run plan validation and style checks; `quality gates`.

## Wave `W02` - backend proof hardening

This Wave strengthens the shared application backend so every filed-history dependency has a registry-derived coverage record, explicit blocker taxonomy, duplicate-current detection, and a non-model-specific proof surface.

### Phase `W02.P05` - dependency inventory surface

Expose a reusable inventory of all registry-declared cross-period requirements so backend, tests, and operator diagnostics can prove coverage before model-specific work starts.

- [x] `W02.P05.S26` - Add cross-period dependency inventory API; `src/aeat/application/calculations/_cross_period_clean_state.py`.
- [x] `W02.P05.S27` - Expose dependency inventory through calculation exports; `src/aeat/application/calculations/__init__.py`.
- [x] `W02.P05.S28` - Cover dependency inventory across every declared cross-period modelo; `src/aeat/application/calculations/tests/test_cross_period_clean_state.py`.

### Phase `W02.P06` - filing-state blocker hardening

Classify unsafe upstream filing states with explicit backend blockers instead of relying on observation absence or a single current lookup result.

- [x] `W02.P06.S29` - Add duplicate-current and superseded filing blockers; `src/aeat/application/calculations/_cross_period_clean_state.py`.
- [x] `W02.P06.S30` - Persist blocker-focused real repository tests; `src/aeat/application/calculations/tests/test_cross_period_clean_state.py`.

## Wave `W03` - full modelo coverage rollout

This Wave applies the shared clean-state backend across every declared cross-period modelo class and proves the registry coverage for annual summaries, prior-period carry-forward, prior-year baselines, and group fan-in.

### Phase `W03.P07` - annual and informative summaries

Prove summary modelos with quarterly or periodic feeder declarations refuse filing-grade workflows unless every feeder filing is clean.

- [x] `W03.P07.S31` - Cover Modelo 390 annual IVA summary clean-state requirements; `src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py`.
- [x] `W03.P07.S32` - Cover retention summary clean-state requirements; `src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py`.
- [x] `W03.P07.S33` - Cover Renta payment-source clean-state requirements; `src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py`.

### Phase `W03.P08` - prior-year and carry-forward modelos

Prove modelos that consume prior-year baselines or prior-period carry-forward use the same clean-state backend and do not bypass it through preview prefill.

- [x] `W03.P08.S34` - Cover Modelo 303 carry-forward clean-state requirements; `src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py`.
- [x] `W03.P08.S35` - Cover Modelo 202 prior-year source clean-state requirements; `src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py`.
- [x] `W03.P08.S36` - Cover patrimonio and foreign-asset prior-year clean-state requirements; `src/aeat/application/calculations/tests/test_cross_period_clean_state.py`.

### Phase `W03.P09` - group fan-in completeness

Bind group aggregate dependencies to expected member coverage so a group modelo cannot become filing-grade from partial member observations.

- [x] `W03.P09.S37` - Add expected member coverage proof for group fan-in; `src/aeat/application/calculations/_cross_period_clean_state.py`.
- [x] `W03.P09.S38` - Cover Modelo 353 incomplete member fan-in refusal; `src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py`.

## Wave `W04` - operator repair and quality closure

This Wave turns blocker verdicts into repairable operator paths, validates full-model behavior through focused gates, and records the residual risks before the feature is closed.

### Phase `W04.P10` - repair diagnostics

Surface typed clean-state blockers with actionable repair commands for importing evidence, refreshing live state, reconciling mismatch, or proving non-applicability.

- [x] `W04.P10.S39` - Add blocker-to-repair diagnostic mapping; `src/aeat/application/modelo/_actions.py`.
- [x] `W04.P10.S40` - Cover operator repair messages for clean-state blockers; `src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py`.

### Phase `W04.P11` - final quality gates

Run focused registry, calculation, modelo workflow, export, and doctor checks and record remaining legal or backend risk.

- [x] `W04.P11.S41` - Run registry cross-dependency tests; `src/aeat/domain/calculations/registry/tests`.
- [x] `W04.P11.S42` - Run calculation clean-state tests; `src/aeat/application/calculations/tests`.
- [x] `W04.P11.S43` - Run modelo workflow clean-state tests; `src/aeat/application/modelo/tests`.
- [x] `W04.P11.S44` - Run doctor and feature index checks; `vaultspec-core doctor`.

## Wave `W05` - member-aware group filing proof

Extend the filing ledger and clean-state proof so group fan-in dependencies prove each expected member filing record, not only member-scoped observations.

### Phase `W05.P12` - member filing identity

Add a durable member axis to upstream filed-history state so multiple group member filings can coexist and be queried independently.

- [x] `W05.P12.S45` - Expose member-scoped filing history queries through the repository contract; `src/aeat/domain/modelos/_protocols.py`.
- [x] `W05.P12.S46` - Add member-scoped filing identity and current-record invariants; `src/aeat/domain/modelos/_filing_record.py`.

### Phase `W05.P13` - member proof wiring

Wire member-scoped filing records into clean-state evaluation, export, and filing so 353 and future group aggregators fail closed on incomplete member filing evidence.

- [x] `W05.P13.S47` - Evaluate group fan-in against member-scoped filing records; `src/aeat/application/calculations/_cross_period_clean_state.py`.
- [x] `W05.P13.S48` - Persist member-scoped clean-state workflow coverage; `src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py`.

## Wave `W06` - external evidence grounding

Strengthen clean-state proof so external-evidence references resolve to imported justificante, CSV register, or live capture artifacts and remain reconciled with filed calculation values.

### Phase `W06.P14` - evidence reference resolution

Resolve filing-record external evidence references through application ports instead of treating the reference metadata itself as sufficient proof.

- [x] `W06.P14.S49` - Add evidence-reference resolution inputs to clean-state evaluation; `src/aeat/application/calculations/_cross_period_clean_state.py`.
- [x] `W06.P14.S50` - Bind justificante and live-capture import artifacts to filing records; `src/aeat/application/modelo/_external_import_actions.py`.

### Phase `W06.P15` - evidence reconciliation tests

Prove CSV-only, live-capture-only, missing-object, stale-object, and reconciled justificante states produce the expected clean-state verdicts.

- [x] `W06.P15.S51` - Cover evidence-reference blockers with real repository tests; `src/aeat/application/calculations/tests/test_cross_period_clean_state.py`.
- [x] `W06.P15.S52` - Cover import-to-filing evidence grounding in workflow tests; `src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py`.

## Wave `W07` - full matrix rollout gates

Turn the dependency inventory into operator-visible coverage and run sharded real-behavior gates across every declared cross-period modelo family.

### Phase `W07.P16` - operator coverage surface

Expose the cross-period inventory and clean-state verdicts through CLI/operator surfaces so incomplete filing history is discoverable before filing.

- [x] `W07.P16.S53` - Expose cross-period dependency inventory in modelo CLI; `src/aeat/entrypoints/cli/_modelo_work_verification_cli.py`.
- [x] `W07.P16.S54` - Cover operator inventory and blocker output; `src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py`.

### Phase `W07.P17` - matrix quality gates

Replace the timed-out broad calculation run with explicit sharded gates covering every declared cross-period target family and final vault hygiene.

- [x] `W07.P17.S55` - Run sharded cross-period calculation family gates; `src/aeat/application/calculations/tests`.
- [x] `W07.P17.S56` - Run final feature index, plan check, doctor, and code-review audit; `quality gates`.

## Description

This plan turns the accepted clean-state ADR into an application-layer enforcement
path. It preserves permissive prefill behavior for explicit diagnostic preview, but
requires proof-backed upstream filing state before cross-period values can support
verification, export, readiness, or filing.

## Steps

## Parallelization

The proof model and repository discovery steps can proceed in parallel with test
fixture inspection. Enforcement wiring depends on the proof service contract. Export
and filing gates depend on verification findings so the same verdict is reported
consistently.

## Verification

The plan is complete when the proof service, calculation or verification wiring,
export and filing gates, and real-behavior tests all pass focused quality gates without
using fakes, mocks, stubs, monkeypatches, skips, or xfails.
