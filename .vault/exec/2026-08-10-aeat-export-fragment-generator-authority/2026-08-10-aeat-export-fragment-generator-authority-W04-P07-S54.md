---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:acb8319e03a3b40e987c0d02046971a18416def1060819321521367c191b92b8'
step_id: 'S54'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Ground and implement the canonical M303 differentiated-sector source taxonomy before projection by researching and approving the source authorities for current-versus-investment, REAGP, rectification, and bienes-inversion regularisation, preserving the chosen closed classification into frozen IVA observations, defining transaction and asset linkage, adjustment ownership, migration and backfill boundaries, and fail-closed behavior, then landing the canonical observation and resolver changes with real ledger, asset, and refusal proofs and no scalar, mapping, label, or slot inference

## Scope

- `src/cadrumo/domain/iva/`
- `src/cadrumo/application/aggregation/`
- `src/cadrumo/domain/calculations/registry/`
- `src/cadrumo/domain/bienes_inversion/`
- `.vault/research/`
- `.vault/adr/`

## Description

- Replace the retired IVA input-kind vocabulary with the closed deduction-fact taxonomy and immutable typed provenance.
- Preserve exact classification through transaction persistence, candidate freezing, registry selection, and aggregation.
- Enforce reciprocal transaction-to-investment-asset identity, profile, year, and sector ownership in the Bienes register.
- Cut transaction, index, and Bienes secure payloads over through one explicit cross-namespace CAS migration.
- Refuse missing authority, ambiguous backfill, old-schema ordinary reads, reused rectifications, and illegal REAGP or rectification combinations.
- Prove strict behavior with real encrypted repositories and evidence-bearing domain fixtures.

## Outcome

The new-only taxonomy is the sole executable IVA deduction authority. Cross-namespace migration validates the complete persisted set before one atomic replacement, production aggregation requires the persisted Bienes authority, and no legacy enum, default backfill, dual read, or unguarded aggregation route remains.

Independent review passed with zero critical, high, medium, or low findings. The affected aggregation lane passed 174 tests, the focused S54 lane passed 76 tests, and the corpus and manipulation lane passed 15 tests. Ruff passed and Basedpyright reported zero errors, warnings, or notes.

## Notes

Initial review found incomplete production reciprocity and namespace-local migration. A second review found retained default backfill and a public low-level aggregation bypass. Each finding was remediated and re-reviewed before closure. Evidence-less corpus fixtures now assert strict missing-classification refusal instead of receiving inferred test classifications.
