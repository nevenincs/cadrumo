---
tags:
  - '#exec'
  - '#schema-driven-wizard'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-schema-driven-wizard-plan]]"
  - "[[2026-05-12-schema-driven-wizard-adr]]"
---

# `schema-driven-wizard` `phase1` `step4`

Landed the `Prompter` protocol and its scripted test-only
implementation.

## What landed

- `src/aeat/application/wizard/_prompter.py` declares the
  `Prompter` `typing.Protocol` (one method
  `ask(question, *, default) -> str`) and the `ScriptedPrompter`
  test-only implementation. `ScriptedPrompter` accepts an iterable
  of canonical-token answers (deque / list / tuple), pops the
  leftmost on every `ask` call, exposes `asked` as a tuple of the
  question ids consumed in call order, and provides `close()` so
  the runtime can assert every scripted answer was consumed at flow
  end.
- `src/aeat/application/wizard/_errors.py` grows the script-control
  hierarchy (`WizardScriptUnderflowError`,
  `WizardScriptOverflowError`) plus the two error classes the later
  Steps will raise (`WizardMissingFlagError`, `WizardCompileError`).
- `src/aeat/core/errors/registry/_application.py` registers the
  four new error codes so the registry-enforcement test stays at
  baseline.
- `src/aeat/application/wizard/test_prompter.py` asserts FIFO order,
  the `asked` witness list, the underflow / overflow contracts,
  and that `ScriptedPrompter` is recognised as a `Prompter` instance
  at runtime (the protocol is `runtime_checkable`).

## Gates cleared

- `uv run --no-sync pytest src/aeat/application/wizard/test_prompter.py`
  is green (6 tests).
- `uv run --no-sync prek run --files <touched paths>` passes ruff,
  format, and ty.

## Not in this Step

- No `QuestionaryPrompter`; lands in the next Step alongside the
  headless TTY smoke test.
- No runtime that consumes the prompter (lands later).
