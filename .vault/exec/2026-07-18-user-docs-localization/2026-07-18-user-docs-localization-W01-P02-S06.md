---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-18'
step_id: 'S06'
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
     The S06 and 2026-07-18-user-docs-localization-plan placeholders are machine-filled by
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
     The Author the all-languages completeness gate asserting every user-scope page catalogue exists with zero untranslated and zero fuzzy entries per target language, failures enumerated by page, language, and counts and ## Scope

- `dev/docs/tests/test_docs_localization.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Author the all-languages completeness gate asserting every user-scope page catalogue exists with zero untranslated and zero fuzzy entries per target language, failures enumerated by page, language, and counts

## Scope

- `dev/docs/tests/test_docs_localization.py`

## Description

- Author the all-languages completeness gate parsing each catalogue with `babel.messages.pofile`, counting untranslated and fuzzy entries per page.
- Structure as one parametrized test per target language so an incomplete language reports a single failure enumerating its incomplete pages with counts, not thousands of per-entry failures.
- Derive the page set from the shared `user_scope_source_pages`, and the target languages from `TARGET_LANGUAGES`.

## Outcome

EXPECTED RED, as intended until the translation wave lands: three failures (one per language), each enumerating all 57 incomplete pages with untranslated and fuzzy counts. No skip or xfail. The gate is collectable and inverts gettext's silent English fallback into a loud per-page refusal.

## Notes

Carries the `unit`/`hex_core`/`docs` marker triple matching sibling docs gates. Because `dev/docs/tests` is not in the default `testpaths`, the red gate is scoped to the docs-check lane and never reds the general unit suite.
