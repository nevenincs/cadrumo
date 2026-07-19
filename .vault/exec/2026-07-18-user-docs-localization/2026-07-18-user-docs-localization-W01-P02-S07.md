---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-19'
step_id: 'S07'
related:
  - "[[2026-07-18-user-docs-localization-plan]]"
---

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
