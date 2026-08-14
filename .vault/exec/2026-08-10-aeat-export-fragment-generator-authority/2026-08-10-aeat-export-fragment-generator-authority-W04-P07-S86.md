---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:f49de4bc728efda001b612e48df94b8a3441ec59ba981aa0e28ad320a9102013'
step_id: 'S86'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Implement the accepted static DP30300 authority boundary before Modelo 303 map authoring. Introduce one typed non-filing inspection projection through ValidatedRegistryAuthority using canonical revision selection and full registry validation, and make export-fragment generation purely static by deleting filing-period, product-identity, casilla-value, rendered-body, instance payload, digest, and total inputs and provenance. Carry the typed DP30300 envelope declaration into generated authority, move static M303 map and generator verification to the inspection projection, and refuse raw-loader, hand-built RegistrySnapshot, filing renderer, calculation, handoff, open-map, default, fake, legacy, and parallel-resolution use of the inspection type

## Scope

- `src/cadrumo/domain/calculations/registry/`
- `dev/registry/`
- `dev/registry/tests/`

## Description

- Add `RegistryRevisionInspection` and canonical authority admission through full registry validation and revision selection.
- Convert static semantic-map validation, joining, generator gates, DP30302 checks, and real 2023 map proof to the inspection projection.
- Delete the snapshot-compatible static map APIs and generator-local filing-instance channels.
- Add semantic AST boundary and legacy-compatibility census coverage, including public and private alias bypasses.

## Outcome

Static generator and map authority now receive only a typed non-filing revision inspection. Filing-instance rendering remains outside this step. The final independent review reports zero critical, high, medium, and low findings.

## Notes

Focused sequential validation passed 63 tests with one upstream openpyxl warning; scoped Ruff passed. S87 loader/tree work and S91 filing-renderer work were excluded from this step's commit.
