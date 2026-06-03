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
