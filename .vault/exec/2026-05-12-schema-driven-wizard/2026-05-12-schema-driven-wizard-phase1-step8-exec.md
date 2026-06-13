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

# `schema-driven-wizard` `phase1` `step8`

Landed the runtime, persistence adapter, verifier, and the Typer
command factory.

## What landed

- `src/aeat/application/wizard/_runner.py` declares `run_flow(flow,
  prompter, *, defaults)` which iterates the flow's sections,
  evaluates `visible_when` against the canonical-token answer set
  collected so far, asks the prompter for visible questions,
  validates each raw answer via `validate_widget_answer`, parses
  the canonical token into the declared `answer_type`, and returns
  `flow.answers_model.model_validate(typed)`. Calls
  `prompter.close()` at the end when the prompter exposes one.
- `src/aeat/application/wizard/_persistence.py` declares
  `serialise_answers(flow, answers) -> dict[str, str]` (canonical-
  token projection over profile-bound questions only),
  `project_answers(flow, values) -> BaseModel` (the reverse
  projection), and `persist_answers(flow, answers, *, state,
  profile_name)` which routes through `set_profile_values` and
  triggers the legacy `save_tax_residence` side-effect when the
  flow writes `tax.residence.ccaa`.
- `src/aeat/application/wizard/_verifier.py` declares
  `WizardCheckSeverity`, `WizardCheckFinding`, `WizardCheckReport`,
  and a closed seven-check tuple consumed by `verify_setup_answers`.
  Each check is a pure function returning one finding; the report
  exposes `has_errors` for downstream gates.
- `src/aeat/application/wizard/_commands.py` declares
  `build_wizard_command(flow)` which returns a closure carrying
  the flow as a `__wizard_flow__` attribute. In `--quiet` mode the
  closure builds a `ScriptedPrompter` from the supplied flag values
  and raises `WizardMissingFlagError` if any required-and-not-
  conditional question is unbound; in `--accept-defaults` mode it
  seeds defaults from the descriptor; otherwise it runs against a
  `QuestionaryPrompter`. `flag_signature(flow)` returns the per-
  question flag triple for CLI registration.
- `src/aeat/application/wizard/_setup_answers.py` gains two
  before-validators that coerce string canonical tokens for the
  `IVARegime` and `CCAA` enum fields so scripted runs can pass the
  upper-cased canonical strings directly.
- `src/aeat/application/wizard/test_setup_runtime.py` exercises
  the runtime against `ScriptedPrompter` for both individual and
  joint declaration paths, asserts conditional skips, and verifies
  the `serialise_answers` ↔ `project_answers` round-trip.
- `src/aeat/application/wizard/test_verifier.py` asserts the
  seven-check shape, the green-case severities, and the
  obligations-inconsistency warning.

## Gates cleared

- `uv run --no-sync pytest src/aeat/application/wizard/` is green
  (72 tests).
- `build_wizard_command(SETUP_FLOW)` returns a callable; the
  attached `__wizard_flow__` matches; `flag_signature(SETUP_FLOW)`
  has 39 rows (one per question).
- `uv run --no-sync prek run --files <touched paths>` passes.

## Not in this Step

- No Typer registration against `aeat config` (W9).
- No deletion of the legacy `aeat init` / `aeat setup` surfaces
  (W11).
- No locale catalogue migration (W10).
