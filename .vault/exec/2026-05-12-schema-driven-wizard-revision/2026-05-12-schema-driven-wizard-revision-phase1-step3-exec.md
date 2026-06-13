---
tags:
  - '#exec'
  - '#schema-driven-wizard-revision'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-schema-driven-wizard-revision-plan]]"
  - "[[2026-05-12-schema-driven-wizard-adr]]"
---

# r3 convert raw assert to typed guard in compiler

## scope

R3 replaces the raw ``assert question.profile_key is not None`` in
``_compile_one`` with an explicit ``raise WizardCompileError(...)``.
The branch is structurally unreachable today (callers filter
``None``-bound questions before invoking ``_compile_one``), but the
typed guard documents the precondition and runs in ``-O`` builds too.

## files owned

- ``src/aeat/application/wizard/_compiler.py``

## acceptance gates run

- ``pytest src/aeat/application/wizard/test_compile.py`` — green (9
  tests)
- ``grep -n '^\s*assert ' src/aeat/application/wizard/_compiler.py``
  returns nothing

## notes

``WizardCompileError`` is already bound to
``errors.error.error_wizard_compile`` in the application error
registry (see ``src/aeat/core/errors/registry/_application.py``); no
new registry entry is required.
