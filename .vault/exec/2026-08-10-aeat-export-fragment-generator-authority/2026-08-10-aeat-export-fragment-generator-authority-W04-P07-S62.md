---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:fb44d21652f7f3c17c2c87996faa54b60b85f1ccbf568233a7bebfcbb1c8231c'
step_id: 'S62'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Establish the revision-owned typed projection_endpoints declaration authority before map generation: load and validate one grounded FilingProjectionRef declaration index for each selected M303 revision, admit semantic-map projection refs only through that index, replace duplicated casilla export_refs admission, integrate numbered declarations with classify_official_boxes, and require generated layouts to biject exactly with declarations without seed layouts or legacy fallback

## Scope

- `src/cadrumo/domain/calculations/registry/`
- `src/cadrumo/_data/registry/aeat/modelos/303/revisions/`
- `dev/registry/`

## Description

- Add strict revision-owned projection declaration schema, loading, indexing, and evidence validation.
- Author 108 exact source-pinned declarations for each of five explicit Modelo 303 revisions.
- Require every numbered declaration to match one projection-only casilla and allow nonnumbered typed endpoints without shadow casillas.
- Admit semantic-map projection references only through declarations.
- Require generated projection fields to biject exactly with declarations.
- Integrate numbered declarations through the sole `classify_official_boxes` authority.
- Delete projection admission through layout fields and `casilla.export_refs`.
- Prove duplicate, missing, full-matrix deletion, cross-revision source, and layout-bijection refusals.

## Outcome

Completed in candidate `90601ebe3f6b107bc03c35dbce1127be1748525f`. Five revisions contain 540 total declarations. Independent validation passed 107 tests; the remediation lane passed 76 tests; real registry inspect loaded 73 modelos and 94 revisions. Ruff, formatting, `ty`, BasedPyright, and diff checks passed. Formal review approved with zero unresolved critical, high, or medium findings.

## Notes

The formal-review High empty-matrix bypass was fixed before closure. No seed layout, legacy fallback, export-ref admission, inferred identity, default, alias, fake, mock, stub, patch, skip, or xfail remains in the implementation.
