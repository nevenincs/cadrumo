---
tags:
  - '#plan'
  - '#cpdefix-followup-allgreen'
date: '2026-07-05'
modified: '2026-07-08'
tier: L3
related:
  - '[[2026-06-30-cpdefix-calculation-allgreen-audit]]'
  - '[[2026-07-04-counterpart-source-provider-adr]]'
  - '[[2026-07-05-modelo-720-prior-year-baseline-plan]]'
  - '[[2026-07-05-cpdefix-followup-allgreen-research]]'
  - '[[2026-07-05-cpdefix-followup-allgreen-adr]]'
---

# `cpdefix-followup-allgreen` plan

## Wave `W01` - Current Truth Refresh

Separate stale closeout blockers from live calculation risks before dispatching coders.

### Phase `W01.P01` - Blocker Inventory

Refresh the cpdefix closeout ledger against current code, vault records, and focused gates.

- [x] `W01.P01.S01` - Record the current stale-versus-live blocker refresh from RAG and focused gates; `.vault/audit/2026-07-05-cpdefix-followup-allgreen-audit.md`.
- [x] `W01.P01.S02` - Reconcile the shared cpdefix testimonial ledger against any new first-level persona roots; `tmp/personas/`.

### Phase `W01.P02` - Agent Dispatch Hygiene

Keep future workers grounded, non-destructive, and scoped to current blockers rather than stale closeout residue.

- [x] `W01.P02.S03` - Brief future code-fixer agents with required vaultspec-rag grounding and no-reexport/no-destructive-git constraints; `.vault/exec/2026-07-05-cpdefix-followup-allgreen/`.

## Wave `W02` - Calculation Edge Hardening

Work only the calculation edges that remain live after the truth refresh.

### Phase `W02.P03` - M347 Source Ownership

Keep M347 summary calculation on the current invoice-owned route unless a reserved-source provider trigger is explicitly approved.

- [x] `W02.P03.S04` - Prove the current M347 summary route remains invoice-owned and does not falsely promote reserved counterpart sources; `src/aeat/_data/registry/aeat/modelos/347/revisions/2008-y-siguientes/`.
- [x] `W02.P03.S05` - Defer repository-backed counterpart provider enrollment until a ledger or purchase-evidence binding trigger is approved; `src/aeat/application/aggregation/_counterpart.py`.

### Phase `W02.P04` - Deferred Source Review

Audit remaining deferred and reserved source-kind edges so live registry declarations never resolve silently blank.

- [x] `W02.P04.S06` - Audit current deferred and reserved source-kind partitions for registry-declared but unenrolled sources; `src/aeat/application/aggregation/_source_mesh.py`.
- [x] `W02.P04.S07` - Select the next triggered deferred detail-row family only if a current persona or operator filing need requires it; `.vault/audit/`.

## Wave `W03` - Verification and Closure

Convert refreshed findings into reproducible gate evidence before making any allgreen claim.

### Phase `W03.P05` - Gate Ladder

Run narrow gates first, then broader calculation gates after live blockers are reconciled.

- [x] `W03.P05.S08` - Run focused gates for import hygiene, source enrollment, M720 row carrier, and M347 counterpart-summary behavior; `src/aeat/tests/`.
- [x] `W03.P05.S09` - Run scoped calculation application and registry test gates before making any allgreen claim; `src/aeat/application/`.

### Phase `W03.P06` - Evidence Closure

Keep the plan honest by pairing checked rows with exec records and vault health evidence.

- [x] `W03.P06.S10` - Scaffold step execution records for completed plan rows and attach verification evidence; `.vault/exec/2026-07-05-cpdefix-followup-allgreen/`.
- [x] `W03.P06.S11` - Regenerate the feature index and run vault checks for the follow-up plan; `.vault/index/`.

## Wave `W04` - Post-Completion M130 Gasto Parity

Reopen the campaign for the current-tree M130 gasto edge where explicit actividad-economica category evidence must not be lost when broader business classification has not yet caught up.

### Phase `W04.P07` - M130 Gasto Category Eligibility

Harden the Modelo 130 casilla 02 gasto path so explicit actividad-economica transaction evidence follows the same eligibility authority as the casilla 01 income path.

- [x] `W04.P07.S12` - Revalidate current M130 gasto actividad-economica eligibility against production aggregation; `src/aeat/application/aggregation/_renta_gasto_ledger.py`.
- [x] `W04.P07.S13` - Cover unclassified actividad-economica gasto and reviewed exclusion behavior with real aggregation tests; `src/aeat/application/aggregation/tests/test_renta_gasto_aggregation.py`.
- [x] `W04.P07.S14` - Record focused verification evidence for the post-completion M130 gasto edge; `.vault/exec/2026-07-05-cpdefix-followup-allgreen/`.

## Wave `W05` - Shared Worktree Resync

Reconcile cpdefix follow-up tracking after concurrent agents relocated source-mesh enrollment tests, preserving no-reexport import hygiene and focused verification evidence before further dispatch.

### Phase `W05.P08` - Relocated Source-Mesh Enrollment

Keep the moved regularizacion enrollment tests grounded on real source imports and verify their current mesh behavior without absorbing unrelated shared worktree edits.

- [x] `W05.P08.S15` - Verify relocated regularizacion source-mesh enrollment gates after the no-reexport cleanup; `src/aeat/application/modelo/tests/test_bienes_inversion_regularizacion_source_mesh_enrollment.py, src/aeat/application/modelo/tests/test_prorrata_regularizacion_source_mesh_enrollment.py`.
- [x] `W05.P08.S16` - Resync relocated regularizacion source-mesh enrollment tests and remove test-export repository import; `src/aeat/application/modelo/tests/test_bienes_inversion_regularizacion_source_mesh_enrollment.py`.

## Wave `W06` - No-Reexport Source Provision

Remove remaining campaign-owned test provisioning through the application adapter export bundle where a concrete real adapter source is available, preserving real-behavior gates for the calculation surface.

### Phase `W06.P09` - Bienes-Inversion Repository Source

Provision capital-goods regularizacion tests from the real bienes-inversion persistence adapter instead of the test-export bundle and verify the calculation/advisory behavior.

- [x] `W06.P09.S17` - Replace bienes-inversion test-export repository imports with the real persistence adapter source; `src/aeat/application/calculations/tests/test_bienes_inversion_regularizacion.py, src/aeat/application/modelo/tests/test_bienes_inversion_advisory.py`.
- [x] `W06.P09.S18` - Replace invoice test-export repository imports with the real persistence adapter source; `src/aeat/application/invoices/tests/test_bulk_import.py, src/aeat/application/filing/tests/test_source_mesh_review.py`.
- [x] `W06.P09.S19` - Replace memoized transaction test-export repository import with the real persistence adapter source; `src/aeat/application/modelo/tests/test_memoized_transaction_catalogue_repository.py`.
- [x] `W06.P09.S20` - Replace renta income aggregation test-export repository imports with real persistence adapter sources; `src/aeat/application/aggregation/tests/test_renta_income_source_jurisdiction_m100.py, src/aeat/application/aggregation/tests/test_impatriado_income_ledger.py`.
- [x] `W06.P09.S21` - Replace LLM telemetry test-export imports with real adapter sources; `src/aeat/application/ledger/tests/test_llm_classify_run_telemetry.py, src/aeat/application/tests/test_diagnostics_telemetry.py`.
- [x] `W06.P09.S22` - Replace ledger evidence test-export storage imports with real adapter sources; `src/aeat/application/ledger/tests/test_evidence_draft.py`.
- [x] `W06.P09.S23` - Replace remaining bucket-event and M145 application test adapter-export imports with direct concrete source imports; `src/aeat/application/modelo/tests/test_m145_communication_events.py; src/aeat/application/modelo/tests/test_m145_communication_create.py; src/aeat/application/modelo/tests/test_review_package_collab_audit.py; src/aeat/application/modelo/tests/test_review_package_feedback.py; src/aeat/application/bucket_maintenance/tests/test_service_archive_restore.py`.
- [x] `W06.P09.S24` - Replace bucket-maintenance storage-helper test adapter-export imports with direct bucket storage imports; `src/aeat/application/bucket_maintenance/tests/test_sandbox.py; src/aeat/application/bucket_maintenance/tests/test_service_disk_usage.py`.
- [x] `W06.P09.S25` - Replace amendment-kind modelo test repository adapter-export imports with direct concrete repository imports; `src/aeat/application/modelo/tests/test_amend_kind_resolution.py`.
- [x] `W06.P09.S26` - Replace remaining calculation and modelo test adapter-export repository imports with direct concrete source imports; `src/aeat/application/calculations/tests/test_modelo_100_base_negativa_general_compensation.py; src/aeat/application/calculations/tests/test_modelo_130_multiyear_renta_enrollment.py; src/aeat/application/calculations/tests/test_pull_path_calculate_path_casilla_parity.py; src/aeat/application/modelo/tests/test_modelo_100_2025_retenciones_credit_fold_in_live.py; src/aeat/application/modelo/tests/test_modelo_202_2025_pago_fraccionado_manual_worked_example.py; src/aeat/application/modelo/tests/test_modelo_200_2024_ejemplo1_tributacion_minima_manual_worked_example.py`.

## Description

## Steps

## Parallelization

## Verification
