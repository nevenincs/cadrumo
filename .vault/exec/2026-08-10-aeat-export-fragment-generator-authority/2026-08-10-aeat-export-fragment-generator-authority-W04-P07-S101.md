---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:c91c78d22ef45023889714681833065e7bf3419f3cc54ac54cc2d35e3adae54f'
step_id: 'S101'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Acquire and register Modelo 185 historical Annex-I authority

## Scope

- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_185/`
- `src/cadrumo/_data/registry/aeat/legal/modelo-185.toml`
- `src/cadrumo/_data/registry/aeat/modelos/185/revisions/2003-2025/`
- `dev/registry/mappings/modelo_185/`
- `dev/registry/render_profiles/modelo_185/`
- `src/cadrumo/application/filing/tests/`

## Description

- Acquire the original official BOE Annex I for Modelo 185.
- Pin its exact bytes, hash, legal identity, and historical scope.
- Prove that the source declares distinct 120-position Type 1 declarante and
  Type 2 declarado records.
- Refuse promotion to record-design authority while the generic parser cannot
  separately parse the rotated Type 2 table.

## Outcome

Progress only; this Step remains open.

Commit `5e10304438b1c18ca0126918db9d471bd63e5f8b` adds the official
`BOE-A-2003-1911` Annex-I PDF: 290582 bytes with SHA-256
`5013b9b86d98a729f0026b1301bae2051c1d5a334cf7334163c170600135d47d`.
The legal and revision records carry the bounded factual source reference, and
the focused source test, direct Modelo 185 validator, source-reference loader,
Ruff, formatting, and diff checks pass.

## Notes

The generic parser sees both official headings but currently folds the rotated
Type 2 table into one falsely complete Type 1 sheet. The source therefore stays
`layout_authority` and `form_spec`; it is not promoted to `record_design`, and
no map, generated tree, coordinate claim, or reuse of the 2026 successor was
added. Completion requires a parser capable of extracting both historical
record types before live-owner mapping and canonical generation.
