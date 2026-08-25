---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:02666acfa2c4973dab59adbb6ebb6c86a70429371bde3b28b1cb2a83bbb9eb6d'
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

Commit `2c327ae64c` then added the official Modelo 165 original 2013 design and
official 2016 update with exact hashes and applicability windows of 2013--2015
and 2016--2022. Canonical corpus sync passes for 68 required URLs and 58
manifests, and the registered-design parser test passes. These are acquisition
facts only; no layout or revision source join was claimed.

No revision span, export layout, or claimed-year verdict changed in that
commit. The whole-tree claimed-year gate therefore remains the acceptance
criterion, not the acquisition count.

## Notes

The M126 and M128 historical PDFs parse to the shipped business geometry, but
the generic coverage validator currently misclassifies the combined label
`Indicador de pÃ¡gina complementaria. Obligatorio En blanco` as a missing
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

Modelo 165 remains unjoined because the official original type-2 table has a
real position gap from 102 to 103, so attaching it to the sole open-ended
layout would overstate coverage. Modelo 270's 2013 BOE annex establishes the
historical era, but the corpus currently has no canonical generic BOE-PDF
acquisition route; the current 2023 AEAT design must not be backdated.
