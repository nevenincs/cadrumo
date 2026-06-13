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

# r14 fold cli root surfaces to config + app only

## scope

R14 closes the standing CLI-root mandate. The root previously exposed
``config``, ``archive``, ``topic``, ``help``, ``app`` (plus the inline
``version`` command). After R14 the root exposes exactly two
subgroups: ``config`` and ``app``. ``archive`` and ``topic`` move
under ``app``; the ``help`` alias for ``topic`` is removed (the
``aeat --help`` flag plus ``aeat app topic <slug>`` already cover the
help-text catalogue surface).

Affected surfaces:

* ``aeat archive export/import`` → ``aeat app archive export/import``
* ``aeat topic [<slug>]`` → ``aeat app topic [<slug>]``
* ``aeat help <slug>`` removed; operators reach the topic catalogue
  through ``aeat app topic``

Locale catalogues, error-registry suggestions, and the archive CLI
tests are updated to the new invocation form.

## files owned

- ``src/aeat/entrypoints/cli/__init__.py`` — root reshape
- ``src/aeat/entrypoints/cli/test_archive_cli.py`` — invoke under
  ``app archive``
- ``src/aeat/locales/{en,es,ca,hu}.yml`` — next-action / topic-not-found
  strings reference ``aeat app topic`` and ``aeat app archive``
- ``src/aeat/core/errors/registry/_application.py`` — default
  suggestions reference the new paths

## acceptance gates run

- ``aeat --help`` renders exactly two subgroups: ``config`` and
  ``app`` (plus the inline ``version`` command, which is a leaf
  command, not a subgroup)
- ``pytest src/aeat/entrypoints/cli/test_archive_cli.py
  src/aeat/entrypoints/cli/test_error_registry_contract.py
  src/aeat/entrypoints/cli/test_cli_surface.py`` — green
- ``prek run --files`` over every owned file — green

## notes

The ``_archive.py`` and ``_topic.py`` modules keep their existing
internal command surface; only the registration parent changed.
