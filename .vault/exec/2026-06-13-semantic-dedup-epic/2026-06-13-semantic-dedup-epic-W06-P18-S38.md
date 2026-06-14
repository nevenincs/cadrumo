---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S38'
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
     The S38 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
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
     The A1b Add a core ISO-datetime parse helper for the Z-suffix fromisoformat sites and ## Scope

- `src/aeat/core/time.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# A1b Add a core ISO-datetime parse helper for the Z-suffix fromisoformat sites

## Scope

- `src/aeat/core/time.py`

## Description

- Added `core.time.parse_iso_datetime` (normalises a trailing `Z` to `+00:00`
  before `datetime.fromisoformat`) and exported it.
- Routed the three `datetime.fromisoformat(x.replace("Z","+00:00"))` sites:
  `transactions._parse_datetime`, `attachments._parse_captured_at`, and the
  Drive modified-time parse.

## Outcome

Committed as `db919bc9d`, tagged `relocation:parse_iso_datetime` (5 files).
Ruff clean (dropped the now-unused `datetime` import in `_google_drive`); 86
time/transactions/attachments/storage tests green. Behaviour-identical.

## Notes

All three sites were peer-clean at edit time.
