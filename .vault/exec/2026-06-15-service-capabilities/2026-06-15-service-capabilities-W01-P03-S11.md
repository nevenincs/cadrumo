---
tags:
  - '#exec'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S11'
related:
  - "[[2026-06-15-service-capabilities-plan]]"
---




# Add a capabilities section to the wizard create/edit flow so opt-in/out is offered at profile creation

## Scope

- `src/aeat/application/wizard`

## Description

- Add `_CAPABILITIES_SECTION` to the setup wizard `SETUP_FLOW` with three CONFIRM questions bound to the `capabilities.*` schema paths: `cloud-evidence-upload` (default off), `llm-vision` (default on), `google-export` (default on).
- Declare the three boolean fields on `SetupAnswers` so the strict (extra-forbid) `project_answers` reverse-projection validates the new questions.
- Add `--<cap>/--no-<cap>` typer.Option entries to `_SETUP_OPTION_INFOS` for the non-interactive flag surface, satisfying the import-time option-coverage assertion.
- Register the f-string-built prompt (`wizard.setup.capabilities.*.prompt`) and flag-help (`wizard.setup.flags.*.help`) keys in `_fstring_registry.py` so scaffold materialises them; set en/es/ca/hu translations through the locales CLI.
- Extend the scripted-prompter sequences in the runtime tests by the three capability answers.

## Outcome

Profile creation/edit now offers opt-in/out of every `ServiceCapability` axis, mirroring the `aeat config profile capabilities set` surface. Locale parity, translation honesty, and the 293-test wizard + locale suites pass; ruff and ty clean on the touched files; the CLI builds. Committed as `3e6573f3e`.

## Notes

Running `aeat.locales scaffold` materialised two in-flight peer keys (`application.modelo.errors.calculate_binding_unknown`, `errors.refused.modelo_calculate_binding_input`) whose referencing `.py` is uncommitted peer WIP. After an initial mistaken removal, the peer's pre-existing working-tree state was fully restored (en authored prose for `calculate_binding_unknown`; placeholders in es/ca/hu and for `modelo_calculate_binding_input`) so no peer work is stranded. The two keys ride in the locale files in their original placeholder/prose form; the peer owns their translation completion.
