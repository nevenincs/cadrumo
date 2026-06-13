---
tags:
  - '#exec'
  - '#modelo-130-pagos-fraccionados-carry'
date: '2026-06-13'
step_id: 'S09'
related:
  - "[[2026-06-13-modelo-130-pagos-fraccionados-carry-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace modelo-130-pagos-fraccionados-carry with a kebab-case feature tag, e.g. #foo-bar.
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

# materialise casilla 05 as a clean Decimal zero with the absent-by-design provenance marker when the span is empty (true 1T, first-filer first quarter, or alta quarter), null-not-error, mirroring the casilla-15 1T path

## Scope

- `src/aeat/domain/calculations/registry/_bindings_previous_filing.py`

## Description

- Confirmed casilla 05 materialises a clean Decimal zero (absent-by-design) when the expanding span is empty: at true 1T the P01 anchor enumeration returns no anchor, so the carry resolves to nothing and the engine emits casilla 05 = 0 marked absent-by-design, mirroring the casilla-15 1T path.
- For a first-filer / alta quarter, the empty owed-quarter set after activity-start suppression yields the same provenance-marked zero via the absent-by-design path.

## Outcome

The empty-span case is null-not-error: casilla 05 = 0 absent-by-design at 1T and for a first filer. Verified by `test_modelo_130_registry.py` absent-by-design case and `test_modelo_130_casilla_05_carry.py::test_first_quarter_carry_resolves_nothing`.

## Notes

No new code path was needed; the P01 empty-span enumeration plus the existing absent-by-design materialisation already deliver the null-not-error invariant.
