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

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace service-capabilities with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S11 and 2026-06-15-service-capabilities-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Add a capabilities section to the wizard create/edit flow so opt-in/out is offered at profile creation and ## Scope

- `src/aeat/application/wizard` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
