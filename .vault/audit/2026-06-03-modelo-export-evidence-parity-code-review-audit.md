---
tags: ['#audit', '#modelo-export-evidence-parity']
date: '2026-06-03'
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
