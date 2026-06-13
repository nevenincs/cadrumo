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

# `schema-driven-wizard` `phase1` `step2`

Landed the five strict frozen descriptor models plus the closed
`WizardWidget` taxonomy.

## What landed

- `src/aeat/application/wizard/_models.py` declares `WizardWidget`
  (StrEnum with seven members: `text`, `secret`, `confirm`, `select`,
  `checkbox`, `path`, `integer`), `WizardCondition`, `WizardChoice`,
  `WizardQuestion`, `WizardSection`, and `WizardFlow`. Every model
  carries `strict=True`, `frozen=True`, `extra="forbid"` per the
  ADR section A skeletons. `WizardQuestion.answer_type` is
  constrained to `type[str] | type[bool] | type[int] | type[Path]`;
  `profile_key` is optional so transient (flow-only) questions are
  legal at the schema level.
- `src/aeat/application/wizard/test_models.py` asserts the strict
  configuration of every model, the seven-member widget set, the
  rejection of non-tuple / empty / wrong-typed inputs, and the
  closed canonical answer-type set.

## Gates cleared

- `uv run --no-sync pytest src/aeat/application/wizard/test_models.py`
  is green (10 tests).
- `uv run --no-sync prek run --files <touched paths>` passes ruff,
  format, and ty type-check.

## Not in this Step

- No per-widget validator dispatch; `_widgets.py` lands next.
- No `Translatable`-prefix model validator; that ties to the
  catalogue prefix and lands when the catalogue does.
- No `Prompter` Protocol or `ScriptedPrompter`; lands later.
