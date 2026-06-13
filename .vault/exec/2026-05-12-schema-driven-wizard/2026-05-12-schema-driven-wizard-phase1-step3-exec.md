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

# `schema-driven-wizard` `phase1` `step3`

Landed the per-widget validators and the dispatch entry point.

## What landed

- `src/aeat/application/wizard/_widgets.py` defines seven pure
  validators (`validate_text`, `validate_secret`, `validate_confirm`,
  `validate_select`, `validate_checkbox`, `validate_path`,
  `validate_integer`) and the single dispatch function
  `validate_widget_answer(question, raw)` that selects the validator
  by `question.widget`. The module re-exports `WizardWidget` for
  external callers. The confirm validator canonicalises every legal
  truth token onto `"true"` / `"false"`; select / checkbox enforce
  closed-choice membership; path expands `~`; integer round-trips
  through `int(...)` to canonicalise the decimal form.
- `src/aeat/application/wizard/_errors.py` declares `WizardError`
  (base) and `WizardValidationError`. Both are bound to
  `ErrorCode`s in the application error registry
  (`ERROR_WIZARD` / `REFUSED_WIZARD_VALIDATION`).
- `src/aeat/core/errors/registry/_application.py` gains the two
  wizard error-code registrations so
  `test_every_aeat_error_subclass_has_a_registered_code` stays at
  its pre-existing baseline.
- `src/aeat/application/wizard/test_widgets.py` exercises every
  widget through the dispatch entry point against valid and invalid
  canonical tokens; the rejection cases assert
  `WizardValidationError` and verify that the error's context
  carries the failing question's prompt key.

## Gates cleared

- `uv run --no-sync pytest src/aeat/application/wizard/test_widgets.py`
  is green (19 tests).
- `uv run --no-sync prek run --files <touched paths>` passes
  ruff, format, and ty.

## Not in this Step

- No questionary dispatch (W5).
- No Typer flag derivation (W8).
- No persistence side effects (W8 / W12).
