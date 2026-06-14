---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S21'
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
     The S21 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
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
     The C2-1 Replace the three private selector-as-dict clones with the canonical selector_as_dict and ## Scope

- `src/aeat/domain/calculations/registry/_binding_selector_utils.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# C2-1 Replace the three private selector-as-dict clones with the canonical selector_as_dict

## Scope

- `src/aeat/domain/calculations/registry/_binding_selector_utils.py`

## Description

- Re-verified at HEAD: three private selector-as-dict clones
  (`_withholding_bindings` `_selector_as_dict`, `_bindings_previous_filing`
  `_selector_as_dict`, `_formula_initial_values` `_binding_selector_as_dict`)
  byte-identical to the canonical `selector_as_dict` in `_binding_selector_utils`.
- Added the aliased canonical import to each (alias preserving the local call
  name, matching the convention in `_bindings`/`_invoice_bindings`/`_ledger_bindings`)
  and deleted the three local defs.
- Removed the now-unused `pydantic.BaseModel` import from `_formula_initial_values`.

## Outcome

Committed as `b88e004c8`, tagged `relocation:selector_as_dict`. Ruff clean on
all three files, registry collect-only clean (2326 tests), 314 focused
binding/selector/withholding/previous_filing/initial_value tests green. No
public shape change.

## Notes

`BaseModel` remained in use in the other two files (selector model classes); only
`_formula_initial_values` lost its sole `BaseModel` user.
