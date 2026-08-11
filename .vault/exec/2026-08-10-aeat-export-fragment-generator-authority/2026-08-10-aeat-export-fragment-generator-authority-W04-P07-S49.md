---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:c83690022efbaeb238b878afb98ddfe4204f8451b2bb96452788d4a91bfc639c'
step_id: 'S49'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Author the M303 two-sector differentiated-deduction canonical row substrate and official casilla 700-735 projection endpoints exactly as S44 decides, including sector identity, typed values, totals, legal/source refs, fixed-slot projection, and no duplicate deduction aggregation path. Refuse applicable filings with incomplete sector data

## Scope

- `src/cadrumo/domain/calculations/registry/`
- `src/cadrumo/_data/registry/aeat/modelos/303/revisions/`
- `src/cadrumo/application/filing/`

## Description

- Emit immutable per-sector and per-deduction-kind contributions from the sole canonical IVA aggregation service after prorrata applies exactly once.
- Project those outputs and canonical Bienes regularisation results into the two official differentiated-sector rows without raw-cuota arithmetic or a second store.
- Author projection-only casillas 700 through 735 with the exact DP30305 geometry for all five explicit revisions.
- Refuse incomplete, duplicate, unknown, inactive, unresolved, unattributable, wrong-owner, or double-consumed sector sources before projection.
- Harden the shared apportionment path so only explicit common-use classification may omit a sector identity.

## Outcome

The five supported M303 revisions expose all 36 differentiated-deduction endpoints as projection-only casillas. Application aggregation remains the sole owner of prorrata arithmetic, while registry projection orders and sums immutable apportioned outputs exactly once. No layout was reactivated and no persistence, manual scalar family, compatibility path, or parallel deduction resolver was added.

The affected broader lane passed 34 tests. Ruff passed and Basedpyright reported zero errors or warnings. Independent review passed with zero critical, high, medium, or low findings.

## Notes

Architecture review clarified that frozen observation cuota is raw and that sector apportionment belongs exclusively to application aggregation. Review then identified silent common-use routing, incomplete sector filtering, duplicate ledger risk, and forgeable regularisation inputs. Each finding was removed and independently re-reviewed before closure.
