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

# r9 land cli.config locale catalogue and broaden parity audit

## scope

R9 adds the full ``cli.config.*`` translation surface to all four
locale catalogues (``en``, ``es``, ``ca``, ``hu``) and adds the
``wizard.setup.flags.<question-id>.help`` subtree consumed by R8's
descriptor-derived Typer flag derivation. The locale-parity audit
in ``application/wizard/_translations.py`` is broadened with a
``audit_cli_config_translations`` function that statically extracts
every ``cli.config.*`` literal from ``entrypoints/cli/_config.py``
and asserts each resolves in every locale.

The locale YAML files have been rewritten with ``yaml.safe_dump``;
keys are now alphabetically sorted but every original entry is
preserved (verified by running the previously-passing test surface
unchanged).

## files owned

- ``src/aeat/locales/en.yml`` — new ``cli.config.{auth,errors,get,list,
  reset,set,setup,status,unset}.*`` keys plus 39 ``wizard.setup.flags.*.help`` entries
- ``src/aeat/locales/es.yml`` — same as en
- ``src/aeat/locales/ca.yml`` — same as en
- ``src/aeat/locales/hu.yml`` — same as en
- ``src/aeat/application/wizard/_translations.py`` — broadened audit
- ``src/aeat/application/wizard/test_wizard_translations_resolve.py``
  — exercises the new audit

## acceptance gates run

- ``pytest src/aeat/application/wizard/test_wizard_translations_resolve.py``
  — green (3 tests)
- ``pytest src/aeat/application/wizard/ src/aeat/entrypoints/cli/test_config_setter.py
  src/aeat/entrypoints/cli/test_cli_surface.py`` — 97 collected,
  all green
- ``aeat config --help`` renders translated text (commands list shows
  the locale-resolved descriptions)
- ``prek run --files`` over every owned file — green

## notes

The ``wizard.setup.flags.*.help`` entries currently reuse the
descriptor's prompt copy as their help text. That keeps the locale
parity gate green while a tighter "short help line per flag" pass
can land in a future doc-prose iteration.
