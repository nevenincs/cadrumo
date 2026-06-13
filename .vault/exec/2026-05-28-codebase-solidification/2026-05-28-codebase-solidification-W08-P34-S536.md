---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: 'S536'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W08.P34.S536`

ENROLL: `ArtefactKind` from `adapters/inbound/borrador/_schema.py` in the PDF corpus fixture generator, replacing 3 bare `artefact_kind == "..."` string comparisons.

- Modified: `src/aeat/tests/fixtures/pdf_corpus/l3_synthetic/_generators/modelo_100_generator.py`

## Description

Three comparisons of the form `params.artefact_kind == "BORRADOR"` / `"PREDECLARACION"` / `"DECLARACION"` were replaced with `ArtefactKind.BORRADOR`, `ArtefactKind.PREDECLARACION`, `ArtefactKind.DECLARACION` after adding `from aeat.adapters.inbound.borrador._schema import ArtefactKind`. The fixture generator was the only production site using bare artefact-kind string literals.

Grep-post-condition: `grep -n "== ['\"]BORRADOR\|== ['\"]PREDECLARACION\|== ['\"]DECLARACION" src/aeat/tests/fixtures/pdf_corpus/l3_synthetic/_generators/modelo_100_generator.py` returned 0 lines.

## Tests

Existing PDF corpus generator smoke tests passed.
