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

# audits-resolution group-b step-7

## scope

Plan row B7: detect the unsupported-console (git-bash on Windows)
case at the `QuestionaryPrompter` boundary and emit a clean
translated message instead of leaking the
`NoConsoleScreenBufferError` traceback.

## changes

`src/aeat/application/wizard/_prompter.py`:

- New `WizardUnsupportedConsoleError(AeatError)` class.
- `QuestionaryPrompter.ask` wraps the widget-specific call in a
  `try / except _NO_CONSOLE_ERRORS`, raising
  `WizardUnsupportedConsoleError` keyed on
  `wizard.errors.unsupported_console` on catch.
- `_NO_CONSOLE_ERRORS` is resolved at module load: the Windows-only
  `prompt_toolkit.output.win32.NoConsoleScreenBufferError` plus
  `OSError` as the POSIX-side fallback.

`src/aeat/entrypoints/cli/_config.py`: the wizard-command wrapper
adds an `except WizardUnsupportedConsoleError` handler that echoes
the translated message to stderr and exits with code 78 (the
project's refused / unsupported-environment code).

Locale catalogues `es / en / ca / hu` gain
`wizard.errors.unsupported_console` with the operator-facing
message pointing them at `--quiet` mode or a different terminal.

`src/aeat/application/wizard/test_prompter.py` adds
`test_questionary_prompter_translates_no_console_error`. The test
drives the prompter with a real `DummyOutput` subclass whose
`write` / `write_raw` raise an `OSError` matching the stand-in
shape; pytest asserts the catch surfaces
`WizardUnsupportedConsoleError`. No mocks / monkeypatches / fakes
of project components — just a real `Output` implementation.

## verification

`pytest src/aeat/application/wizard/test_prompter.py -q` returns 7
passed.

`ruff check` and `ty check` on every touched file green.
