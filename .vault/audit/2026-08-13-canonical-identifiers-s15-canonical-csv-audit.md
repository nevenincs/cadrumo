---
tags:
  - '#audit'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:5bd0079f17003a971ecd4e6a46ad3c27298bc2ebeb38d812678cd6d8fd273702'
related:
  - "[[2026-08-07-canonical-identifiers-adr]]"
  - "[[2026-08-07-canonical-identifiers-reference]]"
---

# `canonical-identifiers` audit: `S15 canonical CSV review`

## Scope

Review `W02.P03.S15` against the accepted CSV-shape decision, canonical identity
owner, public facade, receipt boundary, implementing history, and focused gates.

## Findings

### canonical-owner | low | No competing CSV type or compatibility bridge remains

`AeatCsv` is declared exactly once in the retired module.
It normalises through `normalise_aeat_csv` before constraining the canonical
8-32 uppercase-alphanumeric shape supplied by the retired module.
`src/cadrumo/core/identity/__init__.py` imports it and lists it in `__all__`,
and the receipt schema consumes the facade. The targeted production census found
no `JustificanteCsv` declaration, import, export, private cross-package import,
alias, shim, or competing CSV declaration.

### history-and-verification | low | Delivered implementation remains valid at HEAD

`40c033eb9d` deleted the receipt-local alias and retyped the receipt boundary;
`78b8023a1c` added the direct facade export. The target paths have no working-tree
diff. Focused behavioral verification passed 71 tests, and focused Ruff and Ty
checks both passed.

## Recommendations

Complete later CSV rows at their named consumers and regression boundaries only.
They must import `AeatCsv` directly from `cadrumo.core.identity`; do not restore
a receipt-domain alias or re-export.
