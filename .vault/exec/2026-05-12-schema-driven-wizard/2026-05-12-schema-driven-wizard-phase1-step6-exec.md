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

# `schema-driven-wizard` `phase1` `step6`

Landed the descriptor → `PROFILE_KEYS` projection.

## What landed

- `src/aeat/application/wizard/_compiler.py` declares
  `compile_profile_keys(flows)` per ADR section B. The function
  emits one `ProfileKey` per distinct `WizardQuestion.profile_key`,
  skips `None`-bound questions, sets `requirement = REQUIRED` when
  the question is required and has no `visible_when` (else
  `OPTIONAL`), derives `required_when_key` / `required_when_value`
  from `visible_when` when the parent question is itself
  profile-bound, and raises `WizardCompileError` on duplicate
  bindings across the catalogue.
- `src/aeat/application/wizard/test_compile.py` exercises every
  rule of the projection against a tiny synthetic catalogue: one
  `ProfileKey` per question, none-bound skip, required-vs-optional
  derivation, conditional pair flow-through, transient-parent
  pair-elision, duplicate-key rejection, and the import-time
  purity property (no `os.environ` access, no `Path.read_text`).

## Gates cleared

- `uv run --no-sync pytest src/aeat/application/wizard/test_compile.py`
  is green (9 tests).
- `uv run --no-sync prek run --files <touched paths>` passes ruff,
  format, and ty.

## Not in this Step

- The `WIZARD_FLOWS` catalogue (W7).
- The mutation of `aeat.domain.profile._keys.PROFILE_KEYS` to
  consume the compiler (W7).
