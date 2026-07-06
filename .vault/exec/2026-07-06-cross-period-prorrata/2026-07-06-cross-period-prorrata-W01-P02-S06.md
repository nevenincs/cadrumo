---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S06'
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
     The S06 and 2026-07-06-cross-period-prorrata-plan placeholders are machine-filled by
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
     The implement the encrypted ProrrataRegisterRepository (governed singleton save/load through SecureObjectRepository) on the bienes_inversion adapter pattern and ## Scope

- `src/aeat/adapters/persistence/profile/prorrata_register.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# implement the encrypted ProrrataRegisterRepository (governed singleton save/load through SecureObjectRepository) on the bienes_inversion adapter pattern

## Scope

- `src/aeat/adapters/persistence/profile/prorrata_register.py`

## Description

- Implement the encrypted `ProrrataRegisterRepository` in `src/aeat/adapters/persistence/profile/prorrata_register.py` on the `bienes_inversion` adapter pattern: governed singleton `load`/`save` through `SecureObjectRepository`, FINANCIAL-class ciphertext, empty register when the envelope is absent.
- Add `upsert_entry` (add-or-replace by `(ejercicio, sector_id)` key) plus the module-level `load_prorrata_register` / `save_prorrata_register` / `declare_prorrata_entry` convenience functions.
- Raise `ProrrataRegisterError` on a decrypt/load failure.

## Outcome

The repository round-trips the encrypted register through real SQLite; `upsert_entry` replaces an existing key in place (the ejercicio entry's provisional→settled lifecycle). `ruff` / `ruff format` / `ty` clean.

## Notes

Chose add-or-replace `upsert` semantics over the `bienes_inversion` refuse-duplicate `add`, because one `(ejercicio, sector)` entry is updated across its lifecycle (provisional seed, then definitive settlement) rather than being a distinct-identifier ledger row. The `translated_message` override was dropped from the load-failure error (the registered ErrorCode already carries the message) to avoid a locale scaffold pass that would have swept unrelated peer keys into this change.
