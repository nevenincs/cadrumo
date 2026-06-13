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

# `schema-driven-wizard` `phase1` `step7`

Landed the `WIZARD_FLOWS` catalogue and rewired `PROFILE_KEYS`
to the descriptor projection.

## What landed

- `src/aeat/application/wizard/_catalogue.py` exports `WIZARD_FLOWS`
  as a closed tuple containing the `SETUP_FLOW` descriptor. The
  flow covers every existing `PROFILE_KEYS` entry plus
  `tax.residence.ccaa` and the two formerly-never-prompted
  booleans (`pays_capital_income_with_retencion`,
  `uses_objective_estimation_irpf`). Conditional spouse fields
  are encoded via `visible_when` against `declaration-type=2`;
  `spouse-eu-eea-resident` is conditioned on
  `spouse-non-resident-irpf=true`; `spouse-eu-eea-country` on
  `spouse-eu-eea-resident=true`. `iva-regime` is a `SELECT`
  with the four `IVARegime` values; `tax-residence-ccaa` is a
  `SELECT` projected from `CCAA`.
- `src/aeat/application/wizard/_setup_answers.py` declares the
  typed `SetupAnswers` projection consumed by `SETUP_FLOW`. Cross-
  field invariants live as `model_validator`s.
- `src/aeat/application/wizard/_models.py` grows three
  `WizardFlow` `model_validator`s: a `Translatable`-prefix
  validator that requires every translation key to start with
  `wizard.<flow.id>.`, a unique-question-id validator across the
  flow, and a `visible_when` forward-reference validator.
- `src/aeat/domain/profile/_ccaa.py` extracts the `CCAA`
  `StrEnum` into a dedicated leaf module so the wizard catalogue
  can import it without triggering the descriptor compile cycle.
- `src/aeat/domain/profile/_keys.py` is rewritten to compute
  `PROFILE_KEYS` on first access via `compile_profile_keys`
  against the wizard catalogue; the hand-authored 38-entry tuple
  and the `_key()` helper are deleted. The lazy access pattern
  (a module-level `__getattr__`) breaks the
  domain ↔ application catalogue import cycle.
- `src/aeat/domain/profile/__init__.py` re-exports `CCAA` from
  the leaf module and exposes `PROFILE_KEYS` via a matching
  `__getattr__` so the public API remains a single import
  (`from aeat.domain.profile import PROFILE_KEYS`).
- `src/aeat/application/wizard/test_setup_compiles.py` exercises
  every wiring invariant on the `setup` flow per ADR section I:
  unique question ids, conditional forward references, every
  profile-bound question appearing in `PROFILE_KEYS`, every
  choice value passing its widget validator, and the descriptor
  → `PROFILE_KEYS` projection round-tripping.

## Gates cleared

- `uv run --no-sync pytest src/aeat/application/wizard/test_setup_compiles.py`
  is green (7 tests).
- `uv run --no-sync pytest src/aeat/domain/profile/`: 31 passed,
  1 pre-existing baseline failure (foral-regime error code
  string ERROR vs REFUSED — unrelated to wizard).
- `from aeat.domain.profile import PROFILE_KEYS` returns 39
  entries (38 existing + `tax.residence.ccaa`); the descriptor's
  conditional `required_when_*` cascade is preserved.
- `uv run --no-sync prek run --files <touched paths>` passes.

## Not in this Step

- No Typer command registration (W9).
- No locale migration (W10).
- No deletion of the dead `setup` subpackage (W11).
