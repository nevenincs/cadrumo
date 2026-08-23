---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:437a376a9f5740be5d17b090e15b86033eaeea9e4759f9abf59f4116a6c635e8'
step_id: 'S174'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# propagate row-source identities through calculation replay and review assembly

## Scope

- `src/cadrumo/application/modelo`

## Description

- Carry typed row-source identities from source resolution into calculation-revision persistence.
- Join persisted identities to replayed filing rows by exact binding, row, source kind, and canonical value.
- Refuse missing, orphaned, substituted, and conflicting identity coordinates without exposing opaque identities.
- Preserve identities through export and workflow draft assembly while reminting the draft content address.
- Project deterministic fingerprint-only provenance through the canonical work-review record.

## Outcome

Calculation replay now preserves the encrypted row-source identity attached to each exact row value. A row cannot inherit an authentic identity after its value or attached identity has been substituted, and unidentified M720 rows remain valid.

Ordinary draft and review output never exposes the opaque source-row identity. The real work-review entrypoint publishes only binding, row, source kind, and fingerprint provenance. Independent review concluded with zero findings. Owner replay and revision coverage passed 19 tests; the repository-backed review path passed; Ruff and owned production-file ty checks were clean.

## Notes

The full focused ty invocation that included `_revision_persistence.py` reported five pre-existing protocol-surface diagnostics around `load_revisioned` and `expected_revision_id`. The S174 edits do not alter those protocol declarations; ty passed for all other owned production and test files. S175 retains CLI redaction ownership and S176 retains inventory cohort expansion.
