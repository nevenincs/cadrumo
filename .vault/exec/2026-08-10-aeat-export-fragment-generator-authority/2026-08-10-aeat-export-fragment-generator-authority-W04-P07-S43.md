---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:719b6f07018ffea165d925d8a874f2c3a1c1b5ff78d9dfe1245571cabb082182'
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
- Track raw marker rows before typed conversion so standalone or malformed body, closer, and Variable-total declarations cannot disappear into a fixed record.
- Require exact composition, source order, contiguous prefix geometry, and no fixed-total inference before constructing the typed envelope.
- Add source-level regression coverage for Modelo 200, all five pinned Modelo 303 binaries, and every registered partial-envelope source.

## Outcome

The production parser recognizes the official variable-envelope shape without a modelo or tab-name selector. Every raw body, closing, or Variable-total marker is decisive: it either forms a fully ordered typed envelope or raises `RegistryValidationError`. Ten registered partial sources are an explicit real-source refusal matrix, preventing a broad parseability pass from silently dropping their marker rows. The real Modelo 200 source and each 2023, 2024-early, 2024-late, 2025, and 2026 Modelo 303 binary produce the expected typed envelope; fixed-width generation continues to refuse it without truncation or inferred total.

Reproduced verification: the parser, IR, and generation boundary suite passed 66 tests with two upstream `openpyxl` conditional-formatting warnings; the full `dev/registry/tests` lane passed 191 tests; scoped Ruff passed; scoped BasedPyright reported zero errors, warnings, and notes.

## Notes

The shared worktree carried stranded S43 code and audit scaffolds. They were independently grounded, verified, and completed without touching unrelated peer changes. Repository-wide vault checks retain pre-existing corpus warnings outside this step's scope.
