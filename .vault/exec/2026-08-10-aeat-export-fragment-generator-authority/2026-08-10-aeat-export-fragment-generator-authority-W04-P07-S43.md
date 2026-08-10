---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:b83669dea85a74d07feba72092b5d2b5c692fd06a90f4ec66e72de6b8f531d9d'
step_id: 'S43'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Generalize parser-owned variable-envelope recognition from the exact official body, closing-marker, and Variable-total shape, remove the DP200000 name selector, and prove real Modelo 200 plus all five Modelo 303 binaries while retaining malformed and ambiguous refusal with no extent inference

## Scope

- `src/cadrumo/domain/calculations/registry/`
- `dev/registry/`

## Description

- Replace the `DP200000`-specific parser branch with generic collection of official body, relative-closing, and variable-total markers.
- Require exact body-led composition, source order, contiguous prefix geometry, and no fixed-total inference before constructing the typed envelope.
- Add source-level regression coverage for Modelo 200 and all five pinned Modelo 303 binaries, plus selector absence and malformed/ambiguous refusal cases.
- Confirm the typed parser output remains the one development IR and fixed-generation boundary consume.

## Outcome

The production parser now recognizes the official variable-envelope shape without a modelo or tab-name selector. A `Variable` body cannot silently become a fixed record: missing, wrong, duplicate, mixed, discontinuous, or misordered companion markers raise `RegistryValidationError`. The real Modelo 200 source and each 2023, 2024-early, 2024-late, 2025, and 2026 Modelo 303 binary produce the expected typed envelope; fixed-width generation continues to refuse it without truncation or inferred total.

Reproduced verification: the parser, IR, and generation boundary suite passed 52 tests with two upstream `openpyxl` conditional-formatting warnings; the full `dev/registry/tests` lane passed 191 tests; scoped Ruff passed; scoped BasedPyright reported zero errors, warnings, and notes.

## Notes

The shared worktree carried stranded S43 code and audit scaffolds. They were independently grounded, verified, and completed without touching unrelated peer changes. Repository-wide vault checks retain pre-existing corpus warnings outside this step's scope.
