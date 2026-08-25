---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:a5ad9c68f5a606c46248b789d965384e964b9b993c16332e9eb193e9bd71001b'
step_id: 'S110'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Complete canonical parsing for the partially read Modelo 180 and Modelo 349 designs

## Scope

- `src/cadrumo/domain/calculations/registry/_record_design.py`
- `src/cadrumo/domain/calculations/registry/tests/test_diagram_design_band_recovery_baseline.py`

## Description

- Normalize physically equivalent closed-curve rules in the generic visual-chart parser.
- Group vertically overlapping rule segments into the canonical band geometry without modelo identifiers or fixed coordinates.
- Rebase the focused diagram regression from stale partial counts to the complete official sheet spans.
- Re-run the strict bundled-design completeness gate against the real corpus.

## Outcome

Commit `195b590a91` completes both formerly partial designs through the shared parser: Modelo 180 resolves two 260-position sheets and Modelo 349 resolves four 250-position sheets, with zero skipped positions. The diagram regression passes 4 tests, the record-design parser suite passes 81 tests, and the strict bundled-design gate passes. Ruff, formatting, and diff checks are clean.

## Notes

No modelo-specific fallback, guessed coordinate table, derivative input, or parallel parser was introduced. The repository-wide type command remains red on 527 pre-existing diagnostics; direct checking found no diagnostic on a changed line.
