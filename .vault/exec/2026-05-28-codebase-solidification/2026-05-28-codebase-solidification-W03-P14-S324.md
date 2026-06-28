---
step_id: S324
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W03.P14.S324 — real-behavior tests for canonical home and import purity

## Outcome

`src/aeat/core/test_profile.py` (new, 205 lines) with 12 real-behavior tests:

- `test_setup_answers_canonical_module` — asserts `SetupAnswers.__module__ == "aeat.core.profile"`
- `test_setup_answers_catalogue_uses_core_class` — asserts `SETUP_FLOW.answers_model is SetupAnswers`
- `test_profiles_imports_setup_answers_from_core` — asserts `_profiles.SetupAnswers is core.SetupAnswers`
- `test_profiles_no_deferred_application_imports` — AST walk verifies no function-body imports from `application.wizard` remain in `_profiles.py`
- `test_project_answers_raises_before_registration` — slot raises `ProjectAnswersNotRegisteredError` when empty
- `test_project_answers_registered_after_persistence_import` — importing `_persistence` populates slot with a callable
- `test_setup_answers_minimal_valid` — minimal `SetupAnswers(tax_id=...)` construction succeeds
- `test_setup_answers_iva_regime_string_coercion` — `"GENERAL"` coerces to `IVARegime.GENERAL`
- `test_setup_answers_invalid_iva_regime_raises` — unrecognised token raises `pydantic.ValidationError`
- `test_setup_answers_entity_type_coercion` — `"natural_person"` coerces to `EntityType.NATURAL_PERSON`
- `test_setup_answers_invalid_date_raises` — non-ISO date raises `pydantic.ValidationError`
- `test_setup_answers_valid_date_accepted` — ISO date string accepted without error

`pytestmark = [pytest.mark.unit, pytest.mark.domain_core]`

No mocks, no skips, no tautological assertions.

## Files touched

- `src/aeat/core/test_profile.py` (new)
- `src/aeat/application/wizard/test_setup_answers.py` (updated imports)

## Verification

All 12 tests pass. Ruff zero errors across all modified files.
