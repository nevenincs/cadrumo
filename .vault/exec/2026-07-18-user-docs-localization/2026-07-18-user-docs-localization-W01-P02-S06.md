---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-19'
body_hash: 'sha256:cecd6fd32bea08eef29a833b7e8c9f48a0b08ba6c7bf923a751f10bd846800f1'
step_id: 'S06'
related:
  - "[[2026-07-18-user-docs-localization-plan]]"
---

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
