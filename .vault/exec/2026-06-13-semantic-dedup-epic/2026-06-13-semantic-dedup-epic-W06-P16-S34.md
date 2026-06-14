---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S34'
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
     The S34 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
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
     The D1 Extract one id-truncation display helper for the four ledger-rules sites and ## Scope

- `src/aeat/entrypoints/cli/_ledger_rules_cli.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# D1 Extract one id-truncation display helper for the four ledger-rules sites

## Scope

- `src/aeat/entrypoints/cli/_ledger_rules_cli.py`

## Description

- Added `_short_display_id` to `_ledger_rules_cli` and routed the four identical
  `{id}[:16]...` table-display idioms through it.
- `ruff format` wrapped the two comprehension lines that crossed 120 chars.

## Outcome

Committed as `78c7a6aa9`, tagged `relocation:_short_display_id`. Ruff clean;
ledger contract test green, collection clean.

## Notes

Low-severity intra-module dedup. The three codebase-wide id-truncation
algorithms (`compute_display_id_width` min-unambiguous-prefix, `short_id`
fixed `[-12:]` suffix, this fixed `[:16]` prefix-ellipsis) are constraint-
divergent and intentionally NOT merged per the Pass-3 audit.
