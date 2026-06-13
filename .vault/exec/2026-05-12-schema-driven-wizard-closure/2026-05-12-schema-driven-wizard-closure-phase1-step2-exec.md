---
tags:
  - '#exec'
  - '#schema-driven-wizard-closure'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-schema-driven-wizard-closure-plan]]"
  - "[[2026-05-12-schema-driven-wizard-adr]]"
---

# c2 land cli archive and modelo locale catalogues

## scope

C2 closes the `cli.<group>.*` translation-key leak the second-loop
reviewer flagged. The four locale catalogues stored the key itself as
the value for every `cli.archive.*` and `cli.app.modelo.*` entry, so
`aeat app archive --help` and `aeat app modelo --help` rendered the
raw key strings (`cli.archive.app_help`, `cli.app.modelo.app_help`,
etc.) at runtime in every locale. The wizard audit's R9 sweep stopped
at the `cli.config.*` namespace and missed both groups.

## files owned

- `src/aeat/locales/en.yml`, `src/aeat/locales/es.yml`,
  `src/aeat/locales/ca.yml`, `src/aeat/locales/hu.yml` — every
  literal-key placeholder under `cli.archive.*` (8 keys) and
  `cli.app.modelo.*` (16 keys) replaced with a real translation
  appropriate for the locale. The `cli.topic.*` namespace was
  already translated in all four locales and was not touched
- `src/aeat/application/wizard/_translations.py` — the audit function
  renamed from `audit_cli_config_translations` to
  `audit_cli_translations`. The regex was generalised from
  `cli\.config\.*` to `cli\.<group>\.*`, and the source-walk widened
  from the single `_config.py` file to every `.py` module under
  `aeat.entrypoints.cli/`. The helper `cli_config_keys_referenced_in_source`
  was renamed to `cli_keys_referenced_in_source` for the same reason
- `src/aeat/application/wizard/test_wizard_translations_resolve.py`
  — assertions updated to call the renamed audit; a spot-check now
  verifies a representative key from each newly translated group
  (`cli.archive.app_help`, `cli.app.modelo.app_help`,
  `cli.topic.app_help`) is extracted by the source walker

## acceptance gates run

- `pytest src/aeat/application/wizard/test_wizard_translations_resolve.py`
  — 3 passed. `audit_cli_translations()` returns the empty tuple in
  every locale; the broadened source walk surfaces 86 distinct
  `cli.<group>.*` keys
- `ruff check src/aeat/application/wizard/_translations.py
  src/aeat/application/wizard/test_wizard_translations_resolve.py` —
  passes
- `ty check src/aeat/application/wizard/_translations.py
  src/aeat/application/wizard/test_wizard_translations_resolve.py` —
  passes
- Sanity probe: `tr('cli.archive.app_help', locale=<each>)` and
  `tr('cli.app.modelo.casillas.input_kind_help', locale=<each>)`
  resolve to the locale's translated string in every locale

## notes

The `test_user_help_surfaces_do_not_leak_translation_keys` regression
test from `entrypoints/cli/test_workflow_surface.py` is the
operator-facing leak gate. That test cannot run in isolation right
now because the unstaged `src/aeat/application/workflow/_engine.py`
modification on the worktree (concurrent agent work) raises
`NameError: name 'AeatSession' is not defined` during module import.
The audit-level gate above pins the same contract at the locale
layer; once the concurrent worktree commits land, the CLI-surface
gate will pass without modification.
