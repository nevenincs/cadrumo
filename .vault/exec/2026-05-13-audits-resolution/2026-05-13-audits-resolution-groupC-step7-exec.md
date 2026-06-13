---
tags:
  - '#exec'
  - '#audits-resolution'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-audits-resolution-plan]]"
  - "[[2026-05-13-schema-driven-wizard-ux-audit]]"
---

# audits-resolution group-c step-7

## scope

Plan row C7: surface section / question progress indicators during
the interactive wizard so operators can pace themselves.

## changes

`src/aeat/application/wizard/_runner.py`:

- New `_emit` helper invokes `prompter.emit_progress(text)` when the
  prompter implements the optional hook.
- New `_section_visible_questions` resolves the runtime-visible
  question list per section (after `visible_when` predicates fire).
- `run_flow` emits two progress lines per section: a
  `wizard.progress.section_header` line ("Sección N/M: <title>")
  before the first visible question, and a
  `wizard.progress.question_prefix` line ("(pregunta n/m) ") before
  each visible question.

`src/aeat/application/wizard/_prompter.py`: `QuestionaryPrompter`
gains an `emit_progress(text)` method that prints to stdout.
`ScriptedPrompter` deliberately omits the method so deterministic
tests continue to drive the runner without the progress surface
polluting their captured output.

Locale catalogues `es / en / ca / hu` gain
`wizard.progress.section_header` and
`wizard.progress.question_prefix`. es / en carry real translations;
ca / hu reuse the English text (honesty allowlist applies).

## verification

`pytest src/aeat/application/wizard/test_setup_runtime.py
src/aeat/application/wizard/test_runner_condition.py -q`: 13
passed. The interactive (questionary) path emits the progress
lines via the production `emit_progress` hook; the scripted path
silently ignores progress (no hook implemented).
