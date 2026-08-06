---
step_id: S300
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-07-07
modified: '2026-07-17'
body_hash: 'sha256:986f5eee08e4cc4fd6ab3b49be9aeff977fce829415c7ef8fe75adc42794e5be'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity W09.P41.S300 — objetiva módulos annual profile facts

## Grounding

Required semantic searches were run before implementation:

- `uvx vaultspec-rag search "S300 wizard modulos parameters profile schema estimacion objetiva IAE epigrafe unidades" --type code`
- `uvx vaultspec-rag search "S300"`

The code search identified the M131 módulos manual casillas
(`modulos-epigrafe`, `modulos-1-unidades` through `modulos-7-unidades`) and
the existing `irpf.estimation_regime` / objective-estimation threshold facts in
the user-profile schema. The vault search located the W09/P41 plan inventory and
confirmed no prior S300 execution record existed.

## Outcome

Implemented the profile-side annual data surface for objective-estimation
módulos without duplicating registry coefficient tables.

Added canonical `irpf.objective_estimation_modulos_*` profile facts:

- `objective_estimation_modulos_iae_epigraph`
- `objective_estimation_modulos_module_1_units`
- `objective_estimation_modulos_module_2_units`
- `objective_estimation_modulos_module_3_units`
- `objective_estimation_modulos_module_4_units`
- `objective_estimation_modulos_module_5_units`
- `objective_estimation_modulos_module_6_units`
- `objective_estimation_modulos_module_7_units`

These fields store operator-declared annual values only. Activity-specific
meaning and coefficients remain in the Modelo 131 registry and legal parameter
tables.

## Files Changed

- `src/aeat/_data/registry/aeat/user_profile/schema.toml`
- `src/aeat/core/setup_answers.py`
- `src/aeat/domain/deadlines/_models.py`
- `src/aeat/domain/deadlines/_profiles.py`
- `src/aeat/application/wizard/_catalogue.py`
- `src/aeat/application/wizard/_commands.py`
- `src/aeat/locales/{ca,en,es,hu}.yml`
- `src/aeat/domain/user_profile/tests/test_taxpayer_type_schema_fields.py`
- `src/aeat/domain/deadlines/tests/test_objective_estimation_profile_facts.py`
- `src/aeat/application/wizard/tests/test_setup_runtime.py`
- `src/aeat/application/wizard/tests/test_taxpayer_axes_roundtrip.py`
- `src/aeat/application/user_profile/tests/test_taxpayer_axes_persistence_roundtrip.py`
- `src/aeat/entrypoints/cli/tests/test_profile_create_choice_help.py`

## Verification

- `uv run --no-sync pytest src/aeat/domain/user_profile/tests/test_taxpayer_type_schema_fields.py src/aeat/domain/deadlines/tests/test_objective_estimation_profile_facts.py src/aeat/application/wizard/tests/test_setup_runtime.py src/aeat/application/wizard/tests/test_taxpayer_axes_roundtrip.py src/aeat/application/user_profile/tests/test_taxpayer_axes_persistence_roundtrip.py src/aeat/entrypoints/cli/tests/test_profile_create_choice_help.py -q`
  - Result: 56 passed.
- `uv run --no-sync ruff check src/aeat/core/setup_answers.py src/aeat/domain/deadlines/_models.py src/aeat/domain/deadlines/_profiles.py src/aeat/application/wizard/_catalogue.py src/aeat/application/wizard/_commands.py src/aeat/domain/user_profile/tests/test_taxpayer_type_schema_fields.py src/aeat/domain/deadlines/tests/test_objective_estimation_profile_facts.py src/aeat/application/wizard/tests/test_setup_runtime.py src/aeat/application/wizard/tests/test_taxpayer_axes_roundtrip.py src/aeat/application/user_profile/tests/test_taxpayer_axes_persistence_roundtrip.py src/aeat/entrypoints/cli/tests/test_profile_create_choice_help.py`
  - Result: clean.

## Closure Status

Implementation is verified, but S300 is not marked closed in the plan because
the required command is unavailable in this environment:

- `uv run --no-sync vault plan step check --help`
  - Result: `Failed to spawn: vault` / program not found.
- `uvx vaultspec --help`
  - Result: package not found.

The plan row remains open until `vault plan step check` can be run by an
environment with the VaultSpec CLI installed.
