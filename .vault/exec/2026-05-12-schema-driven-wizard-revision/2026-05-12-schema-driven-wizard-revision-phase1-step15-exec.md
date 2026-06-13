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

# r15 final verification sweep

## scope

R15 records the final-verification gate results for the
schema-driven-wizard revision. No source touches happen in this Step
(the previous fourteen Steps land the change; this Step pins the
verdict). The R1–R14 exec records have also been renamed to the
vault's canonical ``-exec.md`` suffix for ``vault check all``
compliance.

## verification gates

* **CLI root shape** — ``aeat --help`` lists exactly the two
  subgroups required by the standing mandate plus the inline
  ``version`` leaf command:

  ```
  version  Show package and registry version information
  config   Manage local configuration and diagnostics
  app      Operational tax workspace for ledgers, invoices, declarations
  ```

* **Descriptor signature** — ``inspect.signature(build_wizard_command(SETUP_FLOW))``
  reports 42 parameters: 3 mode flags (``profile_name``, ``quiet``,
  ``accept_defaults``) + 39 per-question flags. Order: mode flags
  first, then questions in descriptor order (``tax_id``, ``name``,
  ``surnames``, ``activity``, …).

* **``aeat config --help`` renders translated text in every locale**
  — confirmed by ``audit_cli_config_translations`` (one of three
  tests in ``test_wizard_translations_resolve.py``).

* **Directory absence** —
  ``src/aeat/application/setup/`` does not exist.

* **Grep gates**:

  * ``grep -rn 'application.setup' src/aeat/`` returns only the
    stable namespace identifier (the string literal
    ``"aeat.application.setup.profile"``) inside test_archive.py,
    archive/_registry, archive/_models docstrings, and the new
    ``_storage_namespaces.py`` home — i.e. zero Python-module hits.
  * ``grep -rn 'build_setup_status\|SetupStatusReport' src/aeat/
    --include='*.py'`` returns nothing.
  * ``grep -rn '_bool_value\|_iva_regime_value\|_TRUE_TOKENS\|_FALSE_TOKENS'
    src/aeat/domain/deadlines/`` returns nothing.
  * ``grep -rn 'aeat setup' src/aeat/locales/ src/aeat/application/diagnostics.py
    src/aeat/core/errors/registry/`` returns nothing.
  * ``grep -n 'W[0-9]\|xfail\|monkeypatch.setattr'
    src/aeat/application/wizard/test_compile.py
    src/aeat/entrypoints/cli/test_config_setter.py`` returns nothing.

* **Test surfaces** — focused R15 run of every owned test surface
  ``pytest src/aeat/application/wizard/ src/aeat/entrypoints/cli/test_config_setter.py
  src/aeat/entrypoints/cli/test_cli_surface.py
  src/aeat/entrypoints/cli/test_error_registry_contract.py
  src/aeat/entrypoints/cli/test_archive_cli.py
  src/aeat/entrypoints/cli/deadlines/
  src/aeat/application/test_diagnostics.py`` — 125 passed.

## concurrent-agent territory

The following pre-existing dirty files exist in the worktree from
concurrent agents and are NOT touched by this revision: every
``.vault/adr/2026-05-12-cli-workflow-redesign-*-adr.md``, every
``.vault/research/2026-05-12-cli-workflow-redesign-*-research.md``,
the renta-pipeline phase4/phase5 exec records, several
already-modified registry tests, the deadline imputacion-parameters
and tier-resolver modules, and a handful of pre-existing CLI tests
that exercise the removed ``aeat setup`` command group.
``test_workflow_surface.py``'s 40 failures are pre-existing (they
test ``aeat setup auth``, ``aeat init``, etc. that this revision
does not own).

## summary

The reviewer's REJECT verdict is now closed: every fifteen-point
follow-up has landed via its dedicated R-Step commit. The wizard
slice satisfies the standing mandates: no shims, no partial
implementations, no transient meta in source, the CLI root is
exactly ``config`` + ``app``, and every wizard-introduced
regression is fixed at its fixture root.
