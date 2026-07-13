---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S08'
related:
  - "[[2026-07-13-docs-terminology-search-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-terminology-search with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S08 and 2026-07-13-docs-terminology-search-plan placeholders are machine-filled by
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
     The Author the widened query vocabulary from the coverage report through the Handbook enrolment surfaces, keeping the synonym ratification ratchet and ## Scope

- `src/cadrumo/_data/terminology/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Author the widened query vocabulary from the coverage report through the Handbook enrolment surfaces, keeping the synonym ratification ratchet

## Scope

- `src/cadrumo/_data/terminology/`

## Description

- Curate and promote 20 skill-backed modelo draft concepts to approved:
  036, 111, 115, 123, 131, 180, 184, 190, 193, 200, 202, 210, 232, 309,
  322, 347, 349, 353, 369, 720 (commit `76262fda26`).
- Ground every concept: registry-validated legal_refs, related edges into
  the approved graph, curated Spanish definition with BOE citation and
  preferred/admitted terms, en/ca/hu short descriptions.
- Absorb the glossary generator's src/aeat legal-catalogue path (rename
  straggler that zeroed every legal grounding link).

## Outcome

Approved tier 29 -> 49 concepts; handbook loader clean; all 17 glossary
gates green with 555 permalinked groundings restored. The synonym
ratification ratchet untouched (no candidate bypassed review).

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
