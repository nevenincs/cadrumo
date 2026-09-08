---
tags:
  - '#plan'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
tier: L3
related:
  - '[[2026-09-07-registry-revision-stamp-coverage-adr]]'
  - '[[2026-09-07-registry-revision-stamp-coverage-reference]]'
modified: '2026-09-07'
body_schema: body-v2
body_hash: 'sha256:5403f16df4ebcef2a43823cc5289d8fbf13576072c53ad0a0754c50b142f3b60'
---

# `registry-revision-stamp-coverage` plan

Require the canonical registry coordinate wherever registry-derived values are
persisted, re-confirm every such read through one gate, and delete the proxy and
compatibility paths that the missing coordinate previously required.

## Description

This L3 plan executes `2026-09-07-registry-revision-stamp-coverage-adr`. Wave W01
establishes the canonical contract and primary calculation stamp. Waves W02 and
W03 propagate that contract into the remaining incomplete carriers identified by
`2026-09-07-registry-revision-stamp-coverage-reference`. Wave W04 removes obsolete
behavior and closes coverage. There is no supported unstamped representation:
proof-only storage conversion may emit canonical rows, while absent or unprovable
coordinates are rejected.

## Steps

## Wave `W01` - Canonical contract and calculation spine

Establish the required RegistrySnapshotRef contract, adapt the one shared re-confirmation gate, and stamp CalculationRevision before any dependent carrier is changed.

### Phase `W01.P01` - Canonical stamp contract and shared gate

Make RegistrySnapshotRef the required persisted coordinate and make revision_carry_outcome the only full-coordinate re-confirmation path.

- [x] `W01.P01.S01` - Evolve revision_carry_outcome to require RegistrySnapshotRef and compare its complete coordinate through the law-selected registry authority; `src/cadrumo/application/calculations/revision_carry_gate.py`.
- [x] `W01.P01.S02` - Pass the observation RegistrySnapshotRef through binding prefill without reconstructing coordinate fields; `src/cadrumo/application/calculations/binding_prefill.py`.
- [x] `W01.P01.S03` - Pass the observation RegistrySnapshotRef through relation prefill without reconstructing coordinate fields; `src/cadrumo/application/calculations/relation_prefill.py`.
- [x] `W01.P01.S04` - Map full-coordinate gate refusal onto REGISTRY_REVISION_DIVERGENCE in cross-period clean state; `src/cadrumo/application/calculations/cross_period_clean_state.py`.
- [x] `W01.P01.S05` - Re-confirm prorrata regularizacion source coordinates through revision_carry_outcome; `src/cadrumo/application/calculations/prorrata_regularizacion.py`.
- [x] `W01.P01.S06` - Re-confirm IVA annual-partition source coordinates through revision_carry_outcome; `src/cadrumo/application/calculations/iva_compensation_annual_partition.py`.
- [x] `W01.P01.S07` - Re-confirm bienes-inversion source coordinates through revision_carry_outcome; `src/cadrumo/application/calculations/bienes_inversion_regularizacion.py`.
- [x] `W01.P01.S08` - Re-confirm prorrata seed source coordinates through revision_carry_outcome; `src/cadrumo/application/prorrata_register/seed.py`.
- [x] `W01.P01.S09` - Re-confirm IVA wallet source coordinates through revision_carry_outcome; `src/cadrumo/application/modelo/iva_wallet_gate.py`.
- [x] `W01.P01.S10` - Prove all carry callers share full-coordinate matching and fail closed on divergence; `src/cadrumo/application/calculations/tests/test_carry_gate_parity.py`.

### Phase `W01.P02` - Calculation revision stamping

Stamp CalculationRevision at construction and persistence, then remove its read-side need to infer registry meaning.

- [x] `W01.P02.S11` - Require RegistrySnapshotRef on CalculationRevision as a non-optional persisted field; `src/cadrumo/domain/modelos/calculation_revision.py`.
- [x] `W01.P02.S12` - Stamp CalculationRevision from the already-selected registry snapshot during calculation; `src/cadrumo/application/modelo/calculation_actions.py`.
- [x] `W01.P02.S13` - Preserve the CalculationRevision stamp through reconstruction and external-import creation paths; `src/cadrumo/application/modelo/revision_persistence.py, src/cadrumo/application/modelo/external_import_actions.py`.
- [x] `W01.P02.S14` - Prove the existing generic calculation catalogue persistence strictly deserializes CalculationRevision RegistrySnapshotRef without defaults; `src/cadrumo/adapters/persistence/profile/tests/test_calculation_repository_roundtrip.py`.
- [x] `W01.P02.S15` - Expose the canonical CalculationRevision coordinate in machine-readable calculation payloads; `src/cadrumo/entrypoints/cli/_modelo_payloads.py, src/cadrumo/entrypoints/cli/_modelo_revision_payload_parts.py`.
- [x] `W01.P02.S16` - Re-confirm CalculationRevision through the shared gate before exposing its already write-suppressed M349 values; `src/cadrumo/application/modelo/calculation.py`.
- [x] `W01.P02.S17` - Update CalculationRevision builders and round-trip tests to provide canonical coordinates and reject absent stamps; `src/cadrumo/domain/modelos/tests, src/cadrumo/adapters/persistence/profile/tests/test_calculation_repository_roundtrip.py`.

## Wave `W02` - Derived calculation artefact propagation

Propagate the producing calculation coordinate into every durable report, reconciliation, review, and export-custody envelope after Wave W01 establishes the source stamp.

### Phase `W02.P03` - Verification and reconciliation propagation

Copy and validate the producing calculation coordinate in VerificationReport and ModeloReconciliationRecord.

- [x] `W02.P03.S18` - Require the producing RegistrySnapshotRef on VerificationReport and validate it against its parent CalculationRevision; `src/cadrumo/domain/modelos/verification_report.py, src/cadrumo/adapters/persistence/profile/modelos_verification_reports.py`.
- [x] `W02.P03.S19` - Copy and validate the CalculationRevision coordinate when verification reports are created and loaded; `src/cadrumo/application/modelo/verification_actions.py, src/cadrumo/adapters/persistence/profile/modelos_verification_reports.py`.
- [x] `W02.P03.S20` - Require the producing RegistrySnapshotRef on ModeloReconciliationRecord and copy it during reconciliation; `src/cadrumo/application/modelo/reconciliation_records.py, src/cadrumo/application/modelo/reconciliation.py`.
- [x] `W02.P03.S21` - Prove verification and reconciliation persistence refuses missing or mismatched coordinates; `src/cadrumo/adapters/persistence/profile/tests/test_modelo_reconciliation_repository.py, src/cadrumo/domain/modelos/tests/test_verification_report_roundtrip.py`.

### Phase `W02.P04` - Review and export envelope propagation

Stamp review-package and official-export custody envelopes without modifying official-format bytes.

- [x] `W02.P04.S22` - Require and emit the CalculationRevision RegistrySnapshotRef in ReviewPackageManifest; `src/cadrumo/application/modelo/review_package.py`.
- [x] `W02.P04.S23` - Validate the review package stamp at the shared package-load boundary used by signature, counter-signature, and feedback flows; `src/cadrumo/application/modelo/review_package.py, src/cadrumo/application/modelo/tests/test_review_package_signing.py, src/cadrumo/application/modelo/tests/test_review_package_counter_sign.py, src/cadrumo/application/modelo/tests/test_review_package_feedback.py`.
- [x] `W02.P04.S24` - Complete FilingExportProofCoordinate as a canonical RegistrySnapshotRef-bearing custody coordinate; `src/cadrumo/application/filing/export_proof.py`.
- [x] `W02.P04.S25` - Prove the existing generic export replay persistence strictly validates the completed custody coordinate without changing official bytes; `src/cadrumo/adapters/persistence/profile/tests/test_filing_export_replay_custody.py`.

## Wave `W03` - Cross-period carrier conversion

Convert the Borrador, IVA compensation, and prorrata carrier families to required canonical coordinates and route their consumers through the shared gate after Wave W01.

### Phase `W03.P05` - Borrador and IVA compensation stamping

Require canonical coordinates on Borrador and both IVA compensation carrier shapes and re-confirm them before consumption.

- [x] `W03.P05.S26` - Require RegistrySnapshotRef on Borrador100Snapshot and stamp it from the capture revision; `src/cadrumo/application/live/borrador_100.py`.
- [x] `W03.P05.S27` - Prove Borrador capture and secure round trips reject missing and divergent stamps; `src/cadrumo/application/live/tests/test_borrador_100.py, src/cadrumo/application/live/tests/test_borrador_100_roundtrip.py`.
- [x] `W03.P05.S28` - Require RegistrySnapshotRef on IvaCompensationPeriodState and include it in artefact identity; `src/cadrumo/domain/iva_compensation/carry_forward.py`.
- [x] `W03.P05.S29` - Stamp every IVA compensation period-state producer from its source registry coordinate; `src/cadrumo/application/calculations/iva_compensation_history.py, src/cadrumo/application/calculations/iva_compensation_annual_partition.py`.
- [x] `W03.P05.S30` - Require source and target RegistrySnapshotRef values on IvaCompensationReconciliationDecision; `src/cadrumo/domain/iva_compensation/reconciliation.py`.
- [x] `W03.P05.S31` - Stamp IVA reconciliation decisions at creation and preserve both coordinates through secure storage; `src/cadrumo/application/calculations/iva_wallet_reconciliation.py, src/cadrumo/application/calculations/observations_repository.py`.

### Phase `W03.P06` - Prorrata stamping and carry reads

Require a canonical source coordinate on prorrata register entries and route registry-sensitive carry reads through the shared gate.

- [x] `W03.P06.S32` - Require an explicit tuple of canonical source RegistrySnapshotRef values on ProrrataRegisterEntry, empty only when the entry contains no registry-derived source value; `src/cadrumo/domain/prorrata_register/register.py`.
- [x] `W03.P06.S33` - Stamp registry-derived prorrata entries at seed and settlement creation boundaries while requiring operator-authored entries to declare an explicit empty source-coordinate tuple; `src/cadrumo/application/prorrata_register, src/cadrumo/application/modelo/revision_persistence.py, src/cadrumo/entrypoints/cli/_prorrata_register_cli.py`.
- [x] `W03.P06.S34` - Prove the existing generic prorrata persistence strictly deserializes canonical source coordinates without an opaque fallback; `src/cadrumo/adapters/persistence/profile/tests/test_prorrata_register_roundtrip.py`.
- [x] `W03.P06.S35` - Prove prorrata seed and regularizacion reads reject absent or divergent coordinates through the shared gate; `src/cadrumo/application/calculations/tests/test_prorrata_regularizacion.py, src/cadrumo/application/prorrata_register/tests`.

## Wave `W04` - Compatibility deletion and coverage closure

Remove proxy and deprecated paths, prove already-complete carrier shapes remain canonical, and install regression coverage after all carrier migrations land.

### Phase `W04.P07` - Canonical precedent validation and compatibility deletion

Keep complete carrier shapes coherent while deleting all proxy, optional-stamp, fallback, and deprecated paths made obsolete by required stamps.

- [x] `W04.P07.S36` - Revalidate ModeloDraft as a required canonical RegistrySnapshotRef carrier with no duplicate coordinate path; `src/cadrumo/domain/filing/schema.py, src/cadrumo/adapters/persistence/profile/filing_drafts.py`.
- [x] `W04.P07.S37` - Revalidate ObservationEnvelopePayload as a required stamp carrier and remove any registry-coordinate bypass; `src/cadrumo/application/calculations/observations_repository.py`.
- [x] `W04.P07.S38` - Revalidate M145CommunicationRecord distributed coordinate fields through one RegistrySnapshotRef constructor; `src/cadrumo/application/modelo/m145_communication_records.py`.
- [x] `W04.P07.S39` - Revalidate both M303 annual-summary handoff coordinates through the canonical constructor and shared gate; `src/cadrumo/domain/modelos/calculation_revision_m303_handoff.py, src/cadrumo/application/calculations/m303_regimen_simplificado_annual_summary.py`.
- [x] `W04.P07.S40` - Delete the M349 op-dot and rect-dot prefix classifier and its legacy proxy fixture after authoritative membership lands; `src/cadrumo/application/modelo/calculation.py, src/cadrumo/application/modelo/tests/test_m349_calculation_display_export.py`.
- [x] `W04.P07.S41` - Delete optional-stamp defaults, missing-coordinate advisory branches, the deprecated FiledDeclaracionObservation registry_snapshot_id digest field, and compatibility deserializers exposed by this campaign; `src/cadrumo/application, src/cadrumo/adapters/persistence, src/cadrumo/adapters/outbound/aeat/sede`.
- [x] `W04.P07.S42` - Add anti-compatibility tests that remove each required coordinate from encrypted payloads and prove strict load refusal; `src/cadrumo/adapters/persistence/profile/tests, src/cadrumo/application/calculations/tests`.
- [x] `W04.P07.S48` - Replace FiledDeclaracionObservation's optional opaque registry snapshot digest with required RegistrySnapshotRef and re-confirm every value-consuming read through the shared gate; `src/cadrumo/adapters/outbound/aeat/sede/schema.py, src/cadrumo/adapters/outbound/aeat/sede/declarations_capture.py, src/cadrumo/application/live/filed_observation_persistence.py, src/cadrumo/application/registry/filed_state.py, src/cadrumo/entrypoints/cli/_overview_evidence.py`.

### Phase `W04.P08` - Coverage ratchet and campaign verification

Prove every in-scope durable carrier declares its stamp strategy and run focused and repository-wide quality gates.

- [x] `W04.P08.S43` - Add a carrier-coverage ratchet enumerating every durable registry-derived schema and its canonical stamp strategy; `dev/quality, src/cadrumo/tests`.
- [x] `W04.P08.S44` - Run focused unit and secure-persistence round-trip suites for every migrated carrier; `src/cadrumo`.
- [x] `W04.P08.S45` - Collect integration suites explicitly and run the applicable integration selection without relying on default addopts; `src/cadrumo`.
- [x] `W04.P08.S46` - Run repository format, type, lint, architecture, and unit quality gates and resolve campaign-owned failures; `pyproject.toml, dev/quality`.
- [x] `W04.P08.S47` - Reconcile the coverage reference and accepted ADR against the implemented carrier set and deleted compatibility paths; `.vault/reference/2026-09-07-registry-revision-stamp-coverage-reference.md, .vault/adr/2026-09-07-registry-revision-stamp-coverage-adr.md`.

## Parallelization

Wave W01 lands first because every later carrier depends on its coordinate and
gate contracts. After W01, Waves W02 and W03 have no shared schema ownership and
may proceed independently, although steps within each phase remain ordered from
domain shape through writers, persistence, readers, and tests. Wave W04 starts
only after both carrier waves land; S40 and S41 are deliberately late deletion
steps so no proxy or compatibility path disappears before its canonical consumer
is working.

## Verification

- Every carrier in the coverage reference has a required canonical stamp at its
  application-owned aggregate boundary or is explicitly verified as inheriting
  that stamp from its owning aggregate.
- Removing a required coordinate from each secure payload causes strict load
  refusal; no default, current-revision guess, proxy, shim, or advisory admits it.
- A present coordinate that differs from the law-selected revision is refused by
  `revision_carry_outcome`, and all registry-sensitive readers use that gate.
- M349 row-template membership changes with authoritative registry layout data
  and contains no `op.` or `rect.` prefix classifier.
- Targeted unit and secure round-trip suites pass, integration suites are
  explicitly collected and selected, and repository architecture, format, lint,
  type, and quality gates pass for campaign-owned changes.
- Repository search finds no campaign-owned optional-stamp branch, missing-stamp
  advisory, compatibility deserializer, deprecated proxy, or duplicate
  re-confirmation implementation.
