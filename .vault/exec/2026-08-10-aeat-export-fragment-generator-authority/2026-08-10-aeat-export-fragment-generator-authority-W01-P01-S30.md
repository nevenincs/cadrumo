---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:b3958b3c2ec7ffe364fd6b589ea55f9ccd16abf573c5e9db58bfa5133f92af26'
step_id: 'S30'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Recover official cached positive integers from Total and Total: rows without extent inference, and model DP200000 as a typed variable envelope/composition wrapper outside fixed-width generation with a separately proven composition contract

## Scope

- `src/cadrumo/domain/calculations/registry/`
- `dev/registry/`

## Description

- Recover only cached positive integers following normalized `Total` or `Total:` labels.
- Reject fixed-sheet declared totals that differ from terminal parsed extent without synthesizing missing totals.
- Preserve `DP200000` as one typed variable envelope with fixed prefix, variable body, relative closing suffix, and variable-total anchors.
- Split fixed-record IR from variable-envelope IR and advance the intermediate schema version.
- Preserve complete prefix, body, suffix, and total source metadata through parser-to-IR projection.
- Reject duplicate, mixed, incomplete, geometrically invalid, or misordered envelope composition markers.
- Prove the contract from the hash-pinned Modelo 200/2025 formula and cached workbook views.

## Outcome

The source-derived total mapping is nonempty and measures 76 fixed sheets. Representative anchors retain `DP200001!A119:C119 = 627` and `DP200DID!A49:C49 = 774`; every recovered total equals terminal parsed extent. `DP200000` remains total-free, retains prefix extent 328, body anchor `A14` at offset 329 with length `Variable`, closing anchor `A15` at relative offset `***` with length 18, and variable-total anchor `A16`. The fixed-generation IR contains 76 records, excludes `DP200000`, and exposes exactly one lossless variable envelope.

Focused parser, IR, source-boundary, and semantic-map consumer verification passed with 34 tests. Scoped Ruff passed. Scoped BasedPyright passed with zero errors, warnings, or notes. Independent review found no remaining CRITICAL or HIGH issue; its only residual LOW notes that not every malformed-envelope refusal branch has its own negative test.

## Notes

A shared-branch commit race landed the implementation across peer broad commits while gates were running. Commit `0316ec8f58` contains the parser, schema, facade, IR, initial real-source tests, and IR tests. Commit `38d9447750` contains the strict official-label and positive-integer regression. Commit `4aafa285c1` swept the initial source-boundary refactor and CLI scaffold into unrelated peer work. Scoped commit `e2b4ecf15a` contains the lossless metadata projection, malformed-composition refusal, strengthened source-boundary contract, completed Step Record, and CLI-authored plan closure. History was not rewritten or amended.
