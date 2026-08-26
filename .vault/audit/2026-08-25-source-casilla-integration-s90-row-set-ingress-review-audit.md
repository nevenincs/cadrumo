---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:459b7b89ce9e33e8062ba19a77e1728b914401df9d06c24540f62daa3ac6b0b8'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# `source-casilla-integration` audit: `S90 row-set ingress review`

## Scope

Independent review of S90 commit `a90870cb473`, its governing plan and linked records, S87 through S89 execution records and audits, the new worksheet ingress gateway, the canonical snapshot assembler, and the public worksheet row contracts. The review checked fail-closed unknown-field and cross-group substitution handling, row-coordinate ownership, sparse-row delegation through S87, localization, and that the narrow gateway did not redeclare source resolution, persistence, provenance, or S91 round-trip behavior.

## Findings

### hostile-branch-proof | low | Two implemented ingress refusals lacked direct mutation-resistant tests

The gateway already rejects an undeclared grouping and duplicate `(binding_id, row_index)` cells within one submitted row set, but the original S90 suite did not exercise either branch. Removing either guard could therefore leave the focused suite green. This audit adds real registry-snapshot and public worksheet-record proofs that assert the localized ingress refusal before S87 can supply its different fallback.

No production-path defect was found. The exact-symbol sweep confirms one new ingress gateway delegating to S87's sole snapshot-bound assembler; `CalculationSourceResolution`, `RowSourceIdentity`, `DirectRowMaterializationProvenance`, resolver enrollment, and encrypted revision persistence remain canonical existing surfaces. The gateway neither resolves a source nor persists a row, and S91 remains open.

## Recommendations

No follow-up is open once the two focused hostile-branch tests pass. Retain the live snapshot/public-record shape so mutation of either ingress guard continues to fail deterministically without mocks.
