---
tags:
  - '#exec'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:9bd933c9dadb349b7d76a04b5dd28a5c7e2221a201b222523a9dd41ccac3598c'
step_id: 'S16'
related:
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# Populate model_selectors with the grounded modelo_ tokens from that inventory and prove the per-modelo branch now contributes, leaving _FILING_BASELINE_PROFILE_PATHS in force until it does

## Scope

- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`

## Description

- Wrote a format-preserving `tomlkit` mutation script appending the grounded `modelo_<code>` token to `model_selectors` for the 32 typed `ProfileFieldDefinition` entries identified by P05.S15 (the 53 grounded keys minus the 21 confirmed-derived `renta_family.*` keys), refusing (non-zero exit) if any target path were not found in the live schema rather than silently skipping.
- Ran the mutation: all 32 fields changed, zero already carried the token, zero missing targets.
- Verified the TOML still parses and the registry authority still loads cleanly afterward, and spot-read several mutated field blocks to confirm `tomlkit` preserved surrounding formatting, comments, and field ordering with no collateral edits.
- Proved the fix live against the real `ProfilePreflightService`: a profile carrying no facts is now genuinely assessed for modelo 100 (`per_operation_requirements_assessed=True`) and surfaces `identity.tax_id` as missing with its real grounded `legal_refs` (`orden-hac-1347-2024:art-4`, `orden-hac-277-2026:art-3`) and `modelos=('100',)`; a profile supplying `identity.tax_id` reports the same field no longer missing.
- `identity.tax_id` is the only one of the 32 fields with `required=true`; the other 31 (spouse/dependent/marriage/disability fields, all conditionally required by AEAT rules this campaign did not re-derive) keep `required=false` as shipped, so adding their `modelo_100`/`modelo_303` token is additive wiring with no behavioural effect on `report()`'s required+prefix walk today - a deliberate, honestly-recorded scope boundary, not an oversight. `_FILING_BASELINE_PROFILE_PATHS` at the gate layer is untouched and remains in force, per the Step's own instruction.
- Fixed `test_preflight_ready_with_no_modelo_selectors_matched_is_not_assessed` in `test_services.py`, whose premise (`modelo="100"` selects nothing) was falsified by this Step's own change: retargeted it to `modelo="200"` (a modelo with zero grounded `source=profile` bindings, confirmed via the P05.S15 inventory) and corrected its docstring.
- Added `test_preflight_modelo_100_per_operation_axis_now_contributes` proving both halves live: the axis is assessed and blocks on missing `tax_id`, and assessed and clears when `tax_id` is supplied.
- Corrected the stale docstring on `test_the_shipped_schema_assesses_nothing_for_a_real_modelo` in `test_preflight_reports_unassessed_axis.py` (it still passes unmodified - modelo 303's two grounded fields are both `required=false` - but its claim that "no shipped field declares a modelo_ selector" was no longer true after this Step).

## Outcome

`schema.toml` carries grounded `modelo_036`/`modelo_100`/`modelo_303` tokens on 32 fields. The per-operation axis genuinely contributes for modelo 100 via `identity.tax_id` - the load-bearing case the 2026-08-09 amendment identified. `test_services.py` and `test_preflight_reports_unassessed_axis.py` both updated to stay honest about the new state rather than left to pass vacuously or fail stale.

## Verification

```
uv run --no-sync pytest -p no:cacheprovider -n 0 src/cadrumo/application/user_profile/tests/ src/cadrumo/application/modelo/tests/test_profile_readiness_gate.py src/cadrumo/domain/user_profile/tests/ src/cadrumo/entrypoints/cli/tests/test_config_profile_preflight_scope.py src/cadrumo/entrypoints/cli/tests/test_config_preflight_revision_default.py src/cadrumo/entrypoints/cli/tests/test_modelo_work_readiness_ux.py src/cadrumo/entrypoints/cli/tests/test_modelo_100_readiness_missing_bindings.py src/cadrumo/entrypoints/cli/tests/test_app_quickfile.py -m integration
105 passed, 628 deselected in 102.09s (0:01:42)
```

```
uv run --no-sync pytest -p no:cacheprovider -n 0 src/cadrumo/application/user_profile/tests/test_services.py src/cadrumo/application/modelo/tests/test_profile_readiness_gate.py src/cadrumo/domain/user_profile/tests/ -m unit
190 passed in 21.17s
```

```
uv run --no-sync pytest -p no:cacheprovider -n 0 src/cadrumo/application/user_profile/tests/test_preflight_reports_unassessed_axis.py src/cadrumo/application/modelo/tests/test_modelo_100_2024_profile_coverage.py src/cadrumo/application/modelo/tests/test_profile_binding_real_path.py src/cadrumo/application/user_profile/tests/test_projections.py src/cadrumo/domain/user_profile/tests/test_censo_schema_fields.py src/cadrumo/domain/user_profile/tests/test_maritime_worker_schema_fields.py src/cadrumo/domain/user_profile/tests/test_schema.py src/cadrumo/domain/user_profile/tests/test_taxpayer_type_schema_fields.py -m "unit or integration"
67 passed in 9.03s
```

## Notes

The first inventory pass mis-scoped 11 keys as "schema entries missing" before P05.S15 corrected this to the real 21-key derived-selector explanation; caught and fixed before this Step acted on it, so no wrong schema entries were fabricated. The plan's own P08 phase was found to carry a duplicate five-step block (S24-S28 duplicated verbatim as S29-S33, with a self-referential bug in one of them) while navigating to this Step; removed the duplicate and fixed the self-reference in the same pass, tracked as incidental plan hygiene rather than part of this Step's scope.
