---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:3dcf4efe064a995954235e005e1b12766a48c83b72a73783c459eb3403523574'
step_id: 'S14'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---




# Collapse the duplicated filing-eligibility predicate onto the snapshot-owned check and delete the coverage-ledger duplicate and the by-construction-empty filing gap surface outright, replacing them with matrix-derived gaps proven non-vacuous on a synthetic reviewed corpus, with no superseded ledger surface retained beside the matrix

## Scope

- `src/cadrumo/domain/calculations/registry/_coverage.py`
- `src/cadrumo/domain/calculations/registry/_snapshot.py`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Route coverage review qualification through `check_snapshot_filing_review_tier`.
- Delete `ModelLawCoverageLedger.filing_gaps` and the superseded coverage-owned review predicate.
- Exercise every derived selection coordinate against a revalidated reviewed synthetic corpus whose layout evidence is absent.

## Outcome

The model-law matrix is the sole projection of required coverage gaps. Coverage retains no legal-review status set, membership predicate, or legal-reference review traversal; snapshot construction is the single owner of that authority boundary.

## Notes

The synthetic corpus preserves official-source guidance while changing only the reviewed filing state and the layout-evidence tier. It validates through a fresh `RegistryValidator` before the matrix audit runs. Temporal-evidence rows and the existing M353 emitted-byte expectation were not changed.

An exact symbol sweep leaves no coverage reference to `REVIEWED_REVISION_REVIEW_STATUSES`, `REVIEWED_LEGAL_STATUSES`, `verify_legal_reference`, or `_revision_filing_authority_proof`. The remaining `filing_gaps` projections belong to the separate construct-evidence audit; `ModelLawCoverageLedger.filing_gaps` is absent.
