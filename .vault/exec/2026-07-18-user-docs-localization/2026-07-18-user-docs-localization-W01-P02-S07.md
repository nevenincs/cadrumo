---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-18'
step_id: 'S07'
related:
  - "[[2026-07-18-user-docs-localization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace user-docs-localization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S07 and 2026-07-18-user-docs-localization-plan placeholders are machine-filled by
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
     The Author the language-set parity gate asserting the docs target languages equal the OutputLanguage members minus the English source exactly and ## Scope

- `dev/docs/tests/test_docs_localization.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Author the language-set parity gate asserting the docs target languages equal the OutputLanguage members minus the English source exactly

## Scope

- `dev/docs/tests/test_docs_localization.py`

## Description

- Author the language-set parity gate in the same module, asserting three surfaces agree with the single language authority: the extraction target set, the committed catalogue trees on disk, and the accepted language set the config validates against.
- Read the config's accepted set and default language by evaluating `docs/conf.py` in a subprocess (never `setup()`), mirroring the sibling scope-config helper.

## Outcome

GREEN. `TARGET_LANGUAGES` equals `OutputLanguage` minus English; the committed trees are exactly `{es, ca, hu}`; the config accepts the full `OutputLanguage` set and defaults to English. No language literal is duplicated across the surfaces.

## Notes

None.
