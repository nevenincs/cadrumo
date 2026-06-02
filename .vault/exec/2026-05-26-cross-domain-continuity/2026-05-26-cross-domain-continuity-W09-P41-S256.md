---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-06-02'
step_id: 'S256'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-domain-continuity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     step_id is the originating Step's canonical identifier, e.g. S01.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path. -->

# FU-W07-D surface legal_refs and source_refs on projected M100 casilla values in modelo project verb output payload

## Scope

- `calculation-grounding rule requires every casilla observation to carry its provenance`
- `src/aeat/entrypoints/cli/_modelo.py`

## Description

Audited `modelo project` verb's output payload at
`src/aeat/entrypoints/cli/_modelo.py:5322-5331` for legal_refs and
source_refs surfacing per the calculation-grounding rule.

## Outcome

Already implemented. `casilla_observations` is built as a list of
`CasillaObservationPayload` from `engine_result.entries`, each
carrying `casilla_id`, `value`, `formula_id`, `legal_refs`, and
`source_refs`. The inline comment at lines 5296-5301 references
the grounding rule and explains that input/bound casillas are
operator-supplied and surface in the `m130_accumulated` block.

## Notes

Provenance surfacing is production-active; no additional code
authored by this record.

<!-- Incidents. Data loss. Difficulties (;persistent failiures. Skipped work. Scafolds left in code. Failiures. -->
