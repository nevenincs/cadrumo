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

# `schema-driven-wizard` `phase1` `step5`

Landed the production `QuestionaryPrompter` and the headless TTY
smoke test that exercises every widget kind end-to-end.

## What landed

- `src/aeat/application/wizard/_prompter.py` grows the
  `QuestionaryPrompter` class. The class accepts an optional
  `input` / `output` pair (typed against
  `prompt_toolkit.input.Input` and `prompt_toolkit.output.Output`)
  so tests can drive the prompter through
  `prompt_toolkit.input.create_pipe_input`. Each widget dispatches
  onto the matching questionary primitive: `text` →
  `questionary.text`, `secret` → `questionary.password`, `confirm`
  → `questionary.confirm` (and converts the bool result to
  `"true"` / `"false"`), `select` / `checkbox` use the choice list
  rendered via `tr()`, `path` → `questionary.path`, `integer` →
  `questionary.text` with an `int()` validator that rejects non-
  integer input.
- `src/aeat/application/wizard/test_questionary_smoke.py` exercises
  every widget through a real `QuestionaryPrompter.ask` call
  driven by `create_pipe_input` + `DummyOutput`. The 8 tests cover
  the entire widget enum and assert the canonical-token contract
  holds.

## Gates cleared

- `uv run --no-sync pytest src/aeat/application/wizard/test_questionary_smoke.py`
  is green (8 tests).
- `uv run --no-sync pytest src/aeat/application/wizard/` is green
  (45 tests).
- `uv run --no-sync prek run --files <touched paths>` passes.

## Not in this Step

- No catalogue entry for any flow (W7).
- No Typer command registration (W9).
