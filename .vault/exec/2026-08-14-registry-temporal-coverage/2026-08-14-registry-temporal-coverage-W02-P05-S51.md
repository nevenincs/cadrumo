---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:1e52c3076cf8a475cf4b23663acedec367d9e91e1150e95b2f7b657b7c4e7076'
step_id: 'S51'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---
# Acquire and hash-pin the missing historical design eras or constrain unsupported claimed years for Modelos 126, 128, 165, 181, 184, 270, 308, 309, 341, 353, and 576, and adjudicate Modelo 180 ejercicio 2022 on the presentation axis, until the whole-tree claimed-year layout-design gate passes without backdating a newer design or inventing temporal coverage

## Scope

- `src/cadrumo/_data/corpus/aeat_official/disenos_registro`
- `src/cadrumo/_data/registry/aeat/modelos`
- `src/cadrumo/domain/calculations/registry/tests/test_layout_design_applies_to_claimed_years.py`

## Description

- Reproduce the claimed-year gate before editing and preserve its exact live
  divergence census.
- Use VaultSpec RAG to confirm that S51 is the existing owner and avoid creating
  duplicate per-modelo plan rows.
- Acquire official historical AEAT design bytes for Modelos 126, 128, and 181.
- Record exact hashes, byte counts, applicability windows, and source-catalogue
  enrollment without attaching a source to a revision whose geometry has not
  passed coverage validation.

## Outcome

Progress only; this Step remains open.

Commit `69fdf248bc` added five official PDF artefacts and their canonical
manifest and legal-source records. Modelo 126 now has a 2015--2019 design,
Modelo 128 has a 2015--2019 design, and Modelo 181 has distinct 2009, 2016, and
2017 artefacts. Live SHA-256 and byte-count checks match every recorded value.
Corpus/hash tests pass 6 of 6 and source-grounding plus referential-integrity
tests pass 30 of 30.

No revision span, export layout, or claimed-year verdict changed in that
commit. The whole-tree claimed-year gate therefore remains the acceptance
criterion, not the acquisition count.

## Notes

The M126 and M128 historical PDFs parse to the shipped business geometry, but
the generic coverage validator currently misclassifies the combined label
`Indicador de página complementaria. Obligatorio En blanco` as a missing
required field even though the authored layout emits the exact blank filler at
offset 12. The generic validator and its test are actively owned by another
dirty lane, so this execution did not overwrite them or add a modelo-specific
exception. Reconsider M126/M128 attachment only after that owner lands generic,
mutation-sensitive blank-field normalization and the claimed-year gate passes.

M181 remains unsupported for 2010--2015 and 2018--2021. The acquired historical
files do not justify backdating or closing those years. The remaining S51
modelos likewise require official historical authority or an evidence-backed
source-era/export ruling; narrowing legal selection spans merely to green the
gate is forbidden.
