---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S31'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace semantic-dedup-epic with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S31 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The A2 Replace the two zero-collapse canonical-decimal-string copies with domain canonical_decimal_string and ## Scope

- `src/aeat/application/modelo/_calculation_actions.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# A2 Replace the two zero-collapse canonical-decimal-string copies with domain canonical_decimal_string

## Scope

- `src/aeat/application/modelo/_calculation_actions.py`

## Description

- Re-verified at HEAD: two byte-identical zero-collapse canonical-decimal-string
  copies (`_calculation_actions._canonical_decimal_str`,
  `_calculation_revision._canonical_decimal`) vs canonical
  `domain._identifiers.canonical_decimal_string`.
- Replaced both defs with aliased imports from `domain._identifiers` (matching
  the four existing consumers' import convention), preserving the local call
  names.

## Outcome

Committed as `b0319cc5f`, tagged `relocation:canonical_decimal_string`. Ruff
clean; 136 modelo/calculation tests green. Hash inputs unchanged.

## Notes

Kept the established `from ...domain._identifiers import ...` convention rather
than promoting to a top-level re-export, for consistency with the four existing
consumers (a top-level promotion would be a separate 5-site change).
