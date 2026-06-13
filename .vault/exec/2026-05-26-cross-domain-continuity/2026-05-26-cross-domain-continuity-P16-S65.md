---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
step_id: S65
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity P16.S65

## Outcome

Created `src/aeat/application/modelo/test_profile_binding_real_path.py`
with 8 pin tests covering all 30 M100 2025 `source = "profile"` bindings
against the live `ProfileSchemaDefinition` schema.

- `test_all_profile_key_selectors_resolve_to_schema_paths`: every `profile_key`
  selector names a known `section.key.field.key` path; dead selectors fail.
- `test_profile_model_selector_resolves_via_model_selector_alias`: the CCAA
  `profile_model = TaxResidenceProfile, field = ccaa` selector is found in
  `_profile_fact_index` via the `model_selectors` alias round-trip.
- `test_every_scalar_profile_binding_resolves_to_typed_value`: all scalar
  profile_key and simple profile_model bindings resolve to non-None values
  from the full-population fixture.
- `test_typed_values_match_expected_python_types`: bool / date / str / Decimal
  Python types asserted per binding category; confirms `UserProfileFact`
  coercion is correct before channel routing.
- `test_absent_fact_resolves_to_none_anti_tautology`: taxpayer death-date
  deliberately absent; `_resolve_one` returns `None`, proving no value
  is invented.
- `test_ccaa_binding_selector_yields_model_selector_string`: `profile_binding_selectors`
  yields `"TaxResidenceProfile.ccaa"` (alias, not canonical path) for the
  CCAA binding.
- `test_repeating_collection_selectors_yield_known_alias`: family
  descendant/ascendant bindings (0025-0035, `repeating = True`) each yield a
  `RentaFamilyProfile.*` alias that exists in the schema's `model_selectors`.
- `test_binding_count_is_exactly_30`: structural sentinel pinning the total
  at 30 (19 scalar + 11 repeating-collection).

All 8 tests pass. Ruff clean, pyright 0 errors/warnings.

## Commit

`e337c6af4` — S65: M100 binding-to-schema agreement pin test
