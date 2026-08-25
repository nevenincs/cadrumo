---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:c09325755cd670056019e7023f8f00b0e42c7cd0239b038e6410cda2b258c140'
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

Commit `7f870ade0b` adds the official Modelo 341 `dr341_2005.pdf`, 44020
bytes with SHA-256 `c1c59a...95c3d`, and scopes its factual authority to
2005-02-01 through 2015-12-31. Corpus sync passes for 69 required URLs and 58
manifests, and the focused acquisition/source-enrollment selection passes five
tests. It remains acquisition-only because 2000--2004 has no matching source
and the required geometry comparison is unavailable during the active registry
relocation.

No revision span, export layout, or claimed-year verdict changed in that
commit. The whole-tree claimed-year gate therefore remains the acceptance
criterion, not the acquisition count.

## Notes

The M126 and M128 historical PDFs parse to the shipped business geometry, but
the generic coverage validator currently misclassifies the combined label
`Indicador de pÃƒÂ¡gina complementaria. Obligatorio En blanco` as a missing
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

Modelo 576 remains an evidence blocker: the historical AEAT index exposes no
positional design, while the BOE 2005, 2007, and 2021 annex chain is graphical
form evidence rather than a parser-usable writer contract. The 2007 order is
effective only from 2008 and therefore cannot establish the missing 2007
geometry.

Commit `61cdab0e89` attached the already acquired finite 2015--2019 sources for
Modelos 126 and 128 at revision, layout, and export application-link authority.
It changed no field-level 2020 source reference, selector, grade, geometry, or
export semantics. Generic obligatory-blank coverage and its ordinary-field
negative proof pass, and both historical binaries match the catalogue.

The live whole-tree gate now excludes Modelos 126 and 128 and retains ten
divergences: Modelos 165, 181, 184, 200, 270, 308, 309, 341, 353, and 576.
Modelo 180 is no longer divergent. Modelo 200 is a real 2024-exercise versus
2025-design mismatch governed by the accepted partition ruling and is now
re-carried as a separate temporal Step. S51 remains open until all remaining
divergences are resolved without backdating or invented authority.
