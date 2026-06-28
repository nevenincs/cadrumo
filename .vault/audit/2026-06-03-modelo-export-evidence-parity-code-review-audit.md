---
tags: ['#audit', '#modelo-export-evidence-parity']
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-06-03-modelo-export-evidence-parity-plan]]'
  - '[[2026-06-03-modelo-export-evidence-parity-adr]]'
  - '[[2026-06-03-modelo-export-evidence-parity-research]]'
---

# `modelo-export-evidence-parity` Code Review

## S01-REVIEW-001 | PASS | LedgerFilingEvidence domain record scope is safe to merge

Status: PASS. Reviewed `W01.P01.S01` against the plan, evidence ADR, and research. The domain records are strict frozen Pydantic models, carry the requested tax facts, legal/source references, attachment ids, document-link ids, purchase-evidence reference, manual fact-basis entries, and `snapshot_fingerprint` binding. The accompanying domain test covers strict JSON roundtrip, carrier preservation, fingerprint length validation, and frozen mutation refusal. No Critical or High issues found.

Remaining W01 work is correctly left open: application capture, revision pegging, encrypted revision roundtrip, and the no-silent-omission guard belong to S02-S05.

## S02-REVIEW-001 | PASS | Evidence capture helper stays inside aggregation boundary

Status: PASS. Reviewed `W01.P01.S02` against the plan, evidence ADR, and research. The aggregation layer now projects catalogue transactions into typed `LedgerEvidenceRow` records, binds the bundle to `snapshot_fingerprint`, carries caller-provided manual entries, and exposes `project_manual_fact_basis_entries` for operator casilla inputs. The helper reuses the same catalogue/index and missing-row semantics as `compute_ledger_filing_snapshot`, which keeps the no-silent-omission guard as a separate S05 invariant rather than hiding policy inside capture. Tests cover tax fact projection, fingerprint binding, purchase-evidence and attachment carriers, duplicate contributor ids, missing contributor ids, and blank manual-input omission. No Critical or High issues found.

## S03-REVIEW-001 | PASS | Verified revisions persist evidence pegged to the snapshot

Status: PASS. Reviewed `W01.P01.S03` against the plan and evidence ADR. `CalculationRevision` now has an optional `ledger_filing_evidence` field that is not part of the revision-id hash, preserving legacy/id compatibility. The real verify-flow regression loads the persisted verified revision and asserts that evidence exists, shares the snapshot fingerprint, and includes operator casilla inputs as manual entries. The `_actions.py` verify-time wiring was already present in `HEAD` via shared-worktree commit `b7b6fc46b`; this review treats that committed wiring plus the current field/test closure as the S03 behavioral surface. No Critical or High issues found.

## S04-REVIEW-001 | PASS | Evidence survives encrypted revision storage

Status: PASS. Reviewed `W01.P01.S04` against the encrypted-persistence and no-tautology requirements. The test uses a real isolated runtime profile and `SecureObjectRepository`, persists a `CalculationRevision` with fully populated `LedgerFilingEvidence`, reloads it through `CalculationRevisionCatalogueRepository`, and asserts strict equality plus evidence-field equality. The anti-tautology assertion compares against the same revision with evidence stripped, so the test proves evidence is real persisted state rather than a mirrored expectation. No Critical or High issues found.

## S05-REVIEW-001 | PASS | Evidence contributor coverage is guarded

Status: PASS. Reviewed `W01.P01.S05` against the no-silent-omission requirement. `assert_evidence_covers_snapshot` compares the exact contributor id sets from `LedgerFilingSnapshot.rows` and `LedgerFilingEvidence.rows`, raising `ModeloValidationError` with missing/extra ids on divergence. Aggregation tests cover missing-contributor failure and complete-bundle success. The staged `_actions.py` guard call is limited to importing this helper and invoking it before persisting the verified revision. No Critical or High issues found.

## S06-REVIEW-001 | PASS | SheetExportPlan evidence facet is typed and renderer-neutral

Status: PASS. Reviewed `W02.P02.S06` against the export evidence ADR and workbook parity ADR. The plan now has strict frozen evidence records for per-casilla ledger contributors and manual fact-basis entries, plus an empty default evidence facet on `SheetExportPlan`. The change is renderer-neutral: it only extends the shared plan contract and leaves workbook tab rendering and sidecar emission to S07/S08. Tests cover strict JSON roundtrip, default shape, and snapshot-fingerprint validation. No Critical or High issues found.

## S07-REVIEW-001 | PASS | Offline workbook renders protected evidence tab from the shared plan

Status: PASS. Reviewed `W02.P02.S07` against the export evidence ADR and workbook parity ADR. The offline openpyxl materializer lives beside `SheetExportPlan`, preserves value cells, formula cells, row-set headers, guide metadata, and renders `SheetExportPlan.evidence` into a fixed protected `Evidencia` tab. The implementation does not create a modelo-specific schema path and keeps sidecar emission/reconstitution for S08/S10. Tests serialize a real XLSX payload, load it back through openpyxl, and assert the evidence contributor and manual-basis rows survive with exact string decimal values. No Critical or High issues found.

## S08-REVIEW-001 | PASS | Offline export emits hash-bound machine-readable evidence sidecar

Status: PASS. Reviewed `W02.P02.S08` against the export evidence ADR. The offline export result now carries XLSX bytes plus canonical JSON evidence sidecar bytes generated from `SheetExportPlan.metadata` and the typed `SheetExportPlan.evidence` facet. The sidecar includes a schema version and the actual workbook SHA-256, so it is bound to the workbook artefact rather than a parallel unverified dump. Tests parse the sidecar JSON and verify media types, payload hashes, metadata, contributor rows, and manual basis entries. No Critical or High issues found.

## S09-REVIEW-001 | PASS | Ledger-derived exports require evidence or snapshot reference

Status: PASS. Reviewed `W02.P02.S09` against the export evidence ADR. `export_modelo_revision` now refuses ledger-derived revisions when `source_transaction_ids` is non-empty and both `ledger_filing_evidence` and `ledger_filing_snapshot` are absent. The gate runs immediately after revision load and before any work-unit lookup, draft build, temporary file write, or bucket event emission. The new refusal is registered in the stable error registry. Tests cover the helper shape and a real export-service call that seeds an active profile plus revision repository and asserts no output file is written. No Critical or High issues found.

## S10-REVIEW-001 | PASS | Offline evidence sidecar roundtrip preserves casilla basis

Status: PASS. Reviewed `W02.P02.S10` against the export evidence ADR and plan. The new adapter is generic: it projects bundled `LedgerFilingEvidence` into the workbook `SheetEvidenceFacet` only when the caller supplies transaction-to-casilla attribution, and refuses missing attribution instead of inferring modelo-specific tax semantics. The regression serializes the real offline workbook export, reads the XLSX `Evidencia` tab with openpyxl, validates the JSON sidecar through `OfflineWorkbookEvidenceSidecar`, checks the workbook SHA binding, and asserts contributor/manual casilla basis preservation. No Critical or High issues found.

## S11-REVIEW-001 | PASS | Number-format facet is renderer-neutral and registry-grounded

Status: PASS. Reviewed `W03.P03.S11` against the plan. The change adds a strict `SheetNumberFormat` record and derives `SheetExportPlan.number_formats` from `CasillaDefinition.data_type` for money, integer, and ratio-as-percentage casillas. The regression is grounded in real registry snapshots for every covered modelo and compares plan facets to registry data types rather than a hand-authored expected casilla list. Rendering is intentionally left to later offline/online renderer steps. Gates run: ruff on touched calc-sheets files, focused parity/records tests, and full `src/aeat/application/storage/calc_sheets`. No Critical or High issues found.

## S12-S13-REVIEW-001 | PASS | Section headers and start/final anchors are typed plan facets

Status: PASS. Reviewed landed commit `e725047b5` against `W03.P03.S12` and `W03.P03.S13`. The implementation adds strict `SheetSectionHeader` and `SheetAnchor` records, derives section headers from registry section paths, emits explicit start/final anchors as real value cells, and renders both surfaces bold in the offline workbook. The tests use a real M130 registry snapshot and validate both plan facets and offline XLSX styling. No Critical or High issues found.

## S14-S15-REVIEW-001 | PASS | Registry-grounded offline parity gates are non-tautological

Status: PASS. Reviewed landed commit `db1f5e593` against `W03.P04.S14` and `W03.P04.S15`. The parity test uses bundled registry snapshots and completeness manifests, not a duplicated hand-authored casilla list. S14 compares emitted `(number, segmento)` keys to official manifest keys; S15 compares registry computed casilla ids to actual workbook formula cells. Current full calc-sheets gate passed. No Critical or High issues found.

## S16-REVIEW-001 | PASS | Offline and online renderer cells are compared without network writes

Status: PASS. Reviewed landed commit `efe297f9d` against `W03.P04.S16`. The new conformance test builds one `SheetExportPlan`, serializes the offline openpyxl workbook, and compares the online adapter's generated value/formula/evidence write payloads to the corresponding offline cells. This proves renderer structural conformance without a live Google dependency. Gates run: `test_calc_sheets_offline_online_conformance.py`, `test_calc_sheets_apply_evidence.py`, and ruff on those test surfaces. No Critical or High issues found.

## S17-S18-REVIEW-001 | PASS | IVA and M130 modelos are enrolled in the shared parity gate

Status: PASS. Reviewed landed commit `db1f5e593` against `W04.P05.S17` and `W04.P05.S18`. M303, M390, and M130 are covered through the same parametrized registry-grounded parity test as the other export-capable modelos, with no modelo-specific expected-output table. Current full calc-sheets gate passed. No Critical or High issues found.

## S19-REVIEW-001 | PASS | M100 is enrolled through generic date-binding translation

Status: PASS. Reviewed `W04.P05.S19` against the plan. The implementation adds generic date-binding layout support and translates `age_at_year_end` from the reserved date-binding cell plus layout filing year, avoiding an M100-specific branch. M100 is moved from the explicit translation-gap witness into the same completeness-manifest and live-formula parity gate as the other covered modelos. Gates run: ruff on the touched calc-sheets files, full `src/aeat/application/storage/calc_sheets`, and Google worksheet export/pull roundtrip tests. No Critical or High issues found.

## S20-REVIEW-001 | PASS | M200 is enrolled through generic bracket-dispatch translation

Status: PASS. Reviewed landed commit `4550b9d9d` against `W04.P05.S20`. The translator generalizes the existing CCAA bracket-dispatch path to handle `lookup_bracket_by_entity_type`, and M200 is moved into the same completeness-manifest and live-formula parity gate. No M200-only layout branch is introduced. Current full calc-sheets gate passed. No Critical or High issues found.

## S21-REVIEW-001 | PASS | Per-modelo coverage is explicit and bounded

Status: PASS. Reviewed landed commit `be0ebb08c` against `W04.P05.S21`. The current coverage report is the explicit parametrized parity set in `test_modelo_export_parity`: M130, M303, M390, M111, M115, M200, and M100. The stale translation-gap witness was removed only after M100 and M200 built successfully, so parity is not implied beyond covered registry-backed modelos. No Critical or High issues found.

## S22-REVIEW-001 | HIGH | Step was closed before number-format and start/final rendering existed

Status: REOPENED. Reviewed landed commit `81f4ceeb1` against `W05.P06.S22`. The commit correctly renders the `Evidencia` surface online, but S22 also requires number formats plus start/final anchors to render identically to the offline XLSX. Those facets are not fully implemented yet (`S11` adds only the number-format plan facet; `S12`/`S13` remain open), so S22 was reopened via the vault CLI. Required follow-up: implement renderer parity after S12/S13 land.

## S22-REVIEW-002 | PASS | Online renderer now covers number formats and emphasis

Status: PASS. Reviewed landed commit `ceddb187c` against `W05.P06.S22`. The online apply adapter now emits number-format repeatCell requests from `SheetNumberFormat` and bold emphasis repeatCell requests from section headers plus start/final anchors, while the evidence value surface remains shared with the offline workbook. The conformance tests cover number-format and emphasis request shapes. No Critical or High issues found.

## S23-S24-REVIEW-001 | PASS | Evidence identity and live-write deferral are correctly bounded

Status: PASS. Reviewed landed commit `81f4ceeb1` against `W05.P06.S23` and `W05.P06.S24`. The online adapter consumes the shared `evidence_table` projection and tests assert online value writes match offline evidence cells for the same plan. Live Google network write verification remains delegated to the linked follow-up plan, keeping this campaign offline. Gates run: `test_calc_sheets_apply_evidence.py`, `test_package_module_allowlist.py`, full calc-sheets package, and ruff on touched calc-sheets/google surfaces. No Critical or High issues found for S23/S24.
