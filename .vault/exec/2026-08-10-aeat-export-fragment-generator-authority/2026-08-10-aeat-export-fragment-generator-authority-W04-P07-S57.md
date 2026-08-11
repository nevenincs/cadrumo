---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:3e5e5dd574f121b796b8d8175ccc35ee64b7227fffbd0b47ef5b61d52d5252e8'
step_id: 'S57'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Integrate the strict core-owned discriminated FilingProjectionRef union atomically through CasillaFieldKind.PROJECTION, projection_ref payload semantics, semantic-map and registry schemas and loaders, provenance, generator, renderer dispatch, and the S47-S50 projectors, deleting description-regex, section, slot, offset, numeric, neighbouring-field, string-key, and legacy inference

## Scope

- `src/cadrumo/core/`
- `src/cadrumo/domain/calculations/registry/`
- `src/cadrumo/application/filing/`
- `dev/registry/`

## Description

- Establish one strict core `FilingProjectionRef` union and exact persisted-wire compiler.
- Route semantic-map and registry TOML loaders through the single compiler and reject scalar coercion.
- Carry `projection_ref`, projection-row repeat mode, and occurrence requiredness through schema, provenance, generation, and rendering.
- Route prorrata, differentiated-deduction, simplified-regime, and exonerado-390 rows through exact typed references.
- Delete description, section, offset, numeric-neighbour, string-key, and compatibility inference.
- Separate explicit non-applicability blanks from applicable missing projector output.

## Outcome

The projection boundary now has one canonical typed owner and one exact persisted compiler. Seven closed union members cover every S47-S50 projection family. Both authored loaders reject string, float, and boolean slot coercion. Applicable missing values remain absent and refuse rendering, while each owning family emits blanks only for an explicit non-applicability decision.

Semantic records now own projection-row repetition and strict occurrence requiredness. Both values participate in semantic-map provenance and generated export records. Required records refuse zero occurrences; optional non-claimed records emit no bytes. Generator and renderer proofs cover both required states.

The expanded focused lane passed 171 tests. Scoped Ruff, Ruff formatting, BasedPyright, diff checks, registry verification, and duplication audit passed. Registry verification covered 73 modelos, 94 revisions, 16,800 casillas, and 1,385 formulas. The duplication audit found no clones across 1,506 files. The Spanish-IVA conformance gate passed five tests.

Formal re-review approved the implementation after all three original HIGH findings were closed. The append-only audit retains the findings and their resolution evidence.

## Notes

The first review correctly found permissive Pydantic coercion, blanket blank pre-seeding, and lost DP30302 occurrence identity. The second review found that repeat mode alone was insufficient because generated records still defaulted to required. Each defect was corrected at its canonical authority rather than patched at a consumer. No compatibility alias, tolerant reader, or parallel projector was retained.
