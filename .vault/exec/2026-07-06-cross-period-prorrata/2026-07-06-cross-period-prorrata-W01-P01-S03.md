---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S03'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-period-prorrata with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S03 and 2026-07-06-cross-period-prorrata-plan placeholders are machine-filled by
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
     The declare the ProrrataRegister aggregate holding one entry per (ejercicio, sector) with regime and sector axes present from birth so especial and sectores land without migration (no-legacy-compatibility) and ## Scope

- `src/aeat/domain/prorrata_register/__init__.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# declare the ProrrataRegister aggregate holding one entry per (ejercicio, sector) with regime and sector axes present from birth so especial and sectores land without migration (no-legacy-compatibility)

## Scope

- `src/aeat/domain/prorrata_register/__init__.py`

## Description

- Declare the strict frozen `ProrrataRegister` aggregate in `src/aeat/domain/prorrata_register/__init__.py` holding a tuple of `ProrrataRegisterEntry` rows.
- Reject a register carrying two entries for the same `(ejercicio, sector_id)` key in a model validator.
- Add the `entries_for_ejercicio`, `entry_for`, and `resolve_provisional` lookup helpers.

## Outcome

The aggregate rejects duplicate `(ejercicio, sector)` keys, lets distinct sectors of one ejercicio coexist, and resolves an entry by key. The regime and sector axes are present from birth so prorrata especial and sectores diferenciados land without migration.

## Notes

None.
