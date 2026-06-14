---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S24'
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
     The S24 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
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
     The C6-1 Add stateless active_bucket_id_or_refuse to _common and route the four ledger-family copies through it and ## Scope

- `src/aeat/entrypoints/cli/_common.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# C6-1 Add stateless active_bucket_id_or_refuse to _common and route the four ledger-family copies through it

## Scope

- `src/aeat/entrypoints/cli/_common.py`

## Description

- Re-verified at HEAD (Pass-1 F7 had landed the live-CLI variant; the ledger
  set was untouched): four byte-identical stateless guards plus the
  `_ratios_bucket_and_profile` repeat.
- Added stateless `active_bucket_id_or_refuse` to `_common`; refactored the
  existing `_active_bucket_id_or_bad` to delegate to it (it already ignored its
  `state` arg).
- Replaced the four ledger guards with `from ._common import
  active_bucket_id_or_refuse as _<name>` and routed `_ratios_bucket_and_profile`
  through `_ratios_bucket_id()`; removed the now-unused core/error imports.
- Ran `ruff check --fix` (import order) and `ruff format` (blank-line spacing
  after the def deletions).

## Outcome

Committed as `636acce08`, tagged `relocation:active_bucket_id_or_refuse`
(5 files, net -31 lines). Ruff clean; CLI collect-only clean; CLI tree smoke
build confirms all four aliases resolve to `active_bucket_id_or_refuse`;
ledger interface-contract tests green. No operator-facing behaviour change.

## Notes

The `_active_bucket_id_or_bad(state)` signature is retained (other callers pass
`state`); it now delegates, so the duplicated body is gone without a call-site
sweep.
