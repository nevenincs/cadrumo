---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S20'
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
     The S20 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
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
     The C4-2 Delete the duplicate _display_decimal and import the canonical from _actions_common and ## Scope

- `src/aeat/application/ledger/_review_projection.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# C4-2 Delete the duplicate _display_decimal and import the canonical from _actions_common

## Scope

- `src/aeat/application/ledger/_review_projection.py`

## Description

- Re-verified the duplication at HEAD: the canonical `_display_decimal` lives in
  `_actions_common` (already imported by `_actions_manual`) and was re-declared
  byte-identically in `_review_projection`.
- Added `_display_decimal` to the existing `from ._actions_common import ...`
  line in `_review_projection` and deleted the local re-declaration.
- Removed the now-unused `from decimal import Decimal` import.

## Outcome

Committed as `2448865b1`, tagged `relocation:_display_decimal`. Lint clean,
ledger collect-only clean (298 tests), `test_actions_review.py` 5/5 green. No
public shape change; no peer WIP on the file at edit time.

## Notes

None. Single-file delete-local + import-canonical, behaviour-preserving.
