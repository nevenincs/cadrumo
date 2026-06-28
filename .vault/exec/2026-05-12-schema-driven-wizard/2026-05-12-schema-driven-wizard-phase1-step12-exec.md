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

# `schema-driven-wizard` `phase1` `step12`

Closed the case-insensitive `_normalise_key` asymmetry via a
`ProfileKey.from_key` chokepoint.

## What landed

- `src/aeat/domain/profile/_keys.py` grows
  `ProfileKey.from_key(raw)` classmethod that strips / lowercases /
  folds dashes into dots before the registry lookup. The legacy
  `get_profile_key(key)` is rewritten to delegate to
  `ProfileKey.from_key`, so every consumer that takes a raw operator
  argument resolves through the same canonical normalisation.
- `src/aeat/entrypoints/cli/_config.py` (`config_set`) now uses the
  registered `ProfileKey.key` (the canonical form returned by
  `from_key`) for both the persistence call and the rendered output.
  Operators can write `aeat config set TAX.ID 12345678Z` and
  `aeat config set tax.id 12345678Z` and observe identical
  `ProfileRecord.values` content.
- `src/aeat/entrypoints/cli/test_config_setter.py` —
  `test_config_set_tax_id_is_case_insensitive` flips from
  `xfail(strict=True)` to a hard pass; the test now asserts both
  cases succeed and emit the same canonical key.

## Gates cleared

- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_config_setter.py`
  is green (5 tests, no xfail).
- `uv run --no-sync pytest src/aeat/domain/profile/` passes with
  only the pre-existing baseline failure (the unrelated
  `ForalRegimeError` code category test).
- `uv run --no-sync pytest src/aeat/application/workflow/` is green.
- `uv run --no-sync prek run --files <touched paths>` passes.

## Not in this Step

- `WorkflowState.profiles` typing remains `dict[str, Any]` per ADR
  §G (the typed projection happens via `project_answers`, not by
  re-typing the container).
- `ProfileRecord.values` typing remains `dict[str, str]`.
