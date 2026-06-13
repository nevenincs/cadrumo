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

# r10 sweep dead next-action guidance

## scope

R10 rewrites every ``aeat setup …`` next-action / suggestion / help
string to the descriptor-derived ``aeat config …`` invocation.
Coverage:

* Diagnostics ``DiagnosticCheck.next_action`` strings in
  ``application/diagnostics.py``.
* Error-registry ``default_suggestion`` strings in every
  ``core/errors/registry/_*.py`` module.
* Topic and key-help strings in every locale catalogue.

Replacement map:

* ``aeat setup init --name …`` → ``aeat config setup --profile-name …``
* ``aeat setup status`` → ``aeat config status``
* ``aeat setup auth configure``-family → ``aeat config auth --provider certificate``
* ``aeat setup auth status`` → ``aeat config status``
* ``aeat setup auth providers`` → ``aeat config auth --help``
* ``aeat setup auth login`` → ``aeat config auth --provider certificate``
* ``aeat setup reset <scope> --yes`` → ``aeat config reset --scope all --yes``
* ``aeat setup profile set …`` → ``aeat config set …``

## files owned

- ``src/aeat/application/diagnostics.py``
- ``src/aeat/core/errors/registry/_adapters.py``
- ``src/aeat/core/errors/registry/_application.py``
- ``src/aeat/core/errors/registry/_core.py``
- ``src/aeat/core/errors/registry/_domain.py``
- ``src/aeat/core/errors/registry/_entrypoints.py``
- ``src/aeat/locales/en.yml``
- ``src/aeat/locales/es.yml``
- ``src/aeat/locales/ca.yml``
- ``src/aeat/locales/hu.yml``

## acceptance gates run

- ``grep -rn 'aeat setup' src/aeat/locales/ src/aeat/application/diagnostics.py
  src/aeat/core/errors/registry/`` returns nothing
- ``pytest src/aeat/entrypoints/cli/test_error_registry_contract.py``
  — green (8 tests)
- ``prek run --files`` over every owned file — green

## notes

The plan called out keeping ``cli/_common.py`` off-limits; this Step
respected that.
