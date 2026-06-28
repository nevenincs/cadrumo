---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P06.S01'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P06.S01`

Audited wizard command suggestions for stale `doctor` references and
renamed the CLI root-landing lookup-site key from `quick_start_doctor`
to `quick_start_repair`.

- Modified: `src/aeat/entrypoints/cli/_root_landing.py`

## Description

`src/aeat/application/wizard/_commands.py` carried no `doctor` token
when audited; the file's wizard-flow construction does not reference
the renamed namespace, so no edit was required there. The plan's
P06.S01 also names the CLI root-landing module as the coordinated
lookup-site for the locale key rename a sibling P05 agent is
performing on the four YAML locale files. The lookup-site key was
flipped from `tr("cli.root.landing.quick_start_doctor")` to
`tr("cli.root.landing.quick_start_repair")` so the P05 agent can
rename the YAML key in lockstep. No backwards-compat shim is left.

## Tests

`pytest src/aeat/application/wizard/` was re-run after the edit; the
two surviving failures
(`test_every_cli_translation_resolves_in_every_locale`,
`test_cli_keys_extracted_from_source_are_non_empty`) are the
coordination-window failures and an unrelated pre-existing failure
respectively. The translation-resolution failure clears once the
sibling P05 agent renames the YAML keys.
