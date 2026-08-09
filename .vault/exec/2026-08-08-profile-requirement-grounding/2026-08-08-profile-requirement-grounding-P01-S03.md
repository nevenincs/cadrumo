---
tags:
  - '#exec'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:e08d989a4231ce52369eb35b1426471cbde10031ab7cf3eff1a521c34731774d'
step_id: 'S03'
related:
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# Add roundtrip and anti-tautology tests for the enriched ProfilePreflightRequirement

## Scope

- `src/cadrumo/application/user_profile/tests/`

## Description

Added a model roundtrip test (`ProfilePreflightRequirement.model_validate(requirement.model_dump()) == requirement` with every field populated non-default) and an anti-tautology test (delete `label` from a valid dump, assert `ValidationError`) to `test_services.py`. Also added two grounding-behaviour tests: one proving `_requirement()` resolves the catalogue label (not the raw schema description) for a real field, one proving `modelos`/`legal_refs` reflect the grounding-index union and never the caller's target modelo, and one proving an unknown path never invents a label or grounding.

## Outcome

The anti-tautology test was missing when this Step was first checked; the P04.S11 fresh-context honesty review caught the gap (finding `anti-tautology-coverage-claimed-but-absent`) and it was added in the same session before declaring the campaign complete. `ProfilePreflightRequirement` is not persisted to any boundary (no SQL/TOML/JSON-file write path), so the anti-tautology proof here is "strict validation actually refuses a payload missing the field this campaign made required" rather than the save/mutate/reload-from-disk pattern used for persisted boundaries.

## Verification

`pytest src/cadrumo/application/user_profile/tests/test_services.py -n 0 -m unit` - all pass including `test_preflight_requirement_anti_tautology_dropped_label_refuses_to_load`, `test_preflight_requirement_carries_catalogue_label_and_legal_refs`, `test_preflight_requirement_modelos_reflects_grounding_union_not_the_call_target`, `test_preflight_requirement_never_invents_grounding_for_unknown_path`, and the roundtrip test.

## Notes

Grounded via `2026-08-09-profile-requirement-grounding-audit` finding `anti-tautology-coverage-claimed-but-absent`.
