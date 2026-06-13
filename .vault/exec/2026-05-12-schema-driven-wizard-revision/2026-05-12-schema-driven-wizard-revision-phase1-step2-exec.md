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

# r2 excise historical phrasing from production source

## scope

R2 removes the docstring tokens (``legacy``, ``historical``,
``previously``, ``formerly``, ``replaces``) that describe the
codebase's process state instead of its current behaviour. The plan
explicitly scopes the grep to ``src/aeat/application/wizard/``, but
the same idiom appeared in ``filing/runtime.py``'s docstring and
needed the same cleanup.

## files owned

- ``src/aeat/application/wizard/_verifier.py``
- ``src/aeat/application/wizard/_compiler.py``
- ``src/aeat/application/wizard/_models.py``
- ``src/aeat/application/wizard/_persistence.py``
- ``src/aeat/application/wizard/_status.py``
- ``src/aeat/application/wizard/__init__.py``
- ``src/aeat/application/filing/runtime.py``

## acceptance gates run

- ``grep -rn 'legacy\|historical\|previously\|formerly\|replaces' src/aeat/application/wizard/``
  returns nothing
- ``prek run --files`` over every owned file: green (ruff, ruff format,
  ty type check all passed)

## notes

The ``load_default_filing_profile(path=…)`` parameter retains
``del path`` and its docstring entry; R7 deletes the parameter
outright. R2 only rewrites the docstring to describe the current
behaviour without referencing the parameter's historical signature.
