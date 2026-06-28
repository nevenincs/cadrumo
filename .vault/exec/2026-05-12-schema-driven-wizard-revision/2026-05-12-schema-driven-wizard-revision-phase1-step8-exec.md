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

# r8 descriptor-driven typer flag derivation

## scope

R8 implements ADR section D's "descriptor-derived Typer flag"
mandate. ``build_wizard_command(flow)`` returns a callable whose
``inspect.Signature`` carries one parameter per question in the flow
plus three mode flags. Flag derivation by widget:

* TEXT / SECRET / PATH / INTEGER → ``--<question-id>``;
* CONFIRM → ``--<question-id>/--no-<question-id>`` boolean pair;
* SELECT → ``--<question-id>`` with ``click.Choice([c.value …])``;
* CHECKBOX → repeated ``--<question-id>``.

The CLI entrypoint walks ``WIZARD_FLOWS`` once and registers each
flow with ``target.command(name=flow.id)(wrapped_callable)``. The
wrapper translates ``WizardMissingFlagError`` into a Typer
``BadParameter``. The hand-coded ``config_setup`` body with the
two-flag tax-id/activity surface is gone.

The dead ``flag_signature`` helper and the dead ``widget_supports_flag``
helper are removed; the inspect-based signature is the structural
surface tests now read from.

## files owned

- ``src/aeat/application/wizard/_commands.py``
- ``src/aeat/entrypoints/cli/_config.py``

## acceptance gates run

- ``inspect.signature(build_wizard_command(SETUP_FLOW))`` reports 42
  parameters: 3 mode flags + 39 question flags
- ``aeat config setup --help`` renders every per-question flag plus
  the three mode flags
- ``pytest src/aeat/application/wizard/ src/aeat/entrypoints/cli/test_config_setter.py
  src/aeat/entrypoints/cli/test_cli_surface.py`` — green
- ``prek run --files`` over both owned files — green

## known follow-up

* The help text for each flag is currently the raw translation key
  (``wizard.setup.flags.<question-id>.help``); R9 lands the locale
  catalogue entries for those keys.
* ``test_error_registry_contract.py::test_suggestions_parse_as_valid_cli_commands``
  still fails because error-registry suggestions reference
  ``aeat setup …``; R10 rewrites those strings.
* ``test_workflow_surface.py`` failures are pre-existing (they test
  removed commands like ``aeat setup auth`` and ``aeat init``); not
  in this revision's scope.
