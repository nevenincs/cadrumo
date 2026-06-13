---
tags:
  - '#exec'
  - '#m303-form-vs-semantic-casilla-dual-keying'
date: '2026-06-13'
step_id: 'S02'
related:
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace m303-form-vs-semantic-casilla-dual-keying with a kebab-case feature tag, e.g. #foo-bar.
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

# Pin box 37 deducible source by label-exact match to iva.autorepercutido.intracomunitaria.deducible (AIC leg), documenting the registry self-label collision with iva.autorepercutido.interior.deducible and deferring box 37 to manual only if genuinely ambiguous after confirmation

## Scope

- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-001.toml`

## Description

- Confirmed the registry self-label collision: two casillas self-document as "casilla 37" -- `iva.autorepercutido.interior.deducible` (interior reverse-charge, "oficial casilla 37") and `iva.autorepercutido.intracomunitaria.deducible` (AIC, "oficial casillas 36/37").
- Matched box `37`'s own label "IVA deducible adquisiciones intracomunitarias corrientes - Cuota" to the AIC leg.
- Pinned box `37`'s source to `iva.autorepercutido.intracomunitaria.deducible` by label-exact match, consistent with the 2026-06-13 ADR ratification (Open Question 2) and the 2026-06-09 IVA routing decisions.

## Outcome

- Box 37 is NOT deferred. The label is unambiguous (adquisiciones intracomunitarias), so box 37 is wired to `iva.autorepercutido.intracomunitaria.deducible` in Phase P03.
- No box left manual on ambiguity grounds; both deducible advisory constituents (29/33/37) become computed projections.

## Notes

- No code or TOML changed in this Step; the source pin is recorded in the reference document for Phase P03 to consume.
