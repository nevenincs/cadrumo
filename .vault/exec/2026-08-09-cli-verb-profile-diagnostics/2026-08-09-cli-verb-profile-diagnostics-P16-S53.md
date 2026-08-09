---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:f46030f7bccc16e8a9e34c9ae8c75d6e8bd41acc69d173df29530cdbbb88bc2e'
step_id: 'S53'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Move the date-binding profile-fact resolution into the application layer and expose it through the package facade

## Scope

- `src/cadrumo/application/modelo/_data_inventory.py`

## Description

- Added `profile_requirements_for_binding`, resolving a binding id to the profile facts it consumes and rendering them as grounded requirement text, and exported it from the module and the package facade.
- Placed it beside the checklist's existing binding-to-profile-key mapping, which reads the same registry state.

## Outcome

**This corrects an architecture regression this campaign introduced.**

The date-binding guidance originally resolved the binding inside the CLI root, which meant two `resources().modelos.authority` reads landed in a module an architecture gate budgets at exactly zero. The gate's own wording is unambiguous: registry authority reads must move OUT of the CLI root, not multiply. Raising the budget would have been the wrong fix twice over - it would defeat a deliberate constraint, and it would leave registry resolution in a transport layer.

Moving it here is the fix the gate was asking for. The binding definitions are registry state, this package already reads them for the same purpose, and the entrypoint keeps only the addressing.

The best-effort contract is preserved and now stated on the function itself: an unresolvable snapshot, an unmatched binding id, or a binding naming no profile key all return the empty string so the caller keeps whatever guidance it had.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_missing_date_binding_guidance_grounding.py src/cadrumo/entrypoints/cli/tests/test_architecture_boundaries.py -m "unit or integration" -n 0 -q
    10 passed in 26.02s

## Notes

The regression was invisible to every check this campaign ran until the campaign-wide suite reached the architecture gate. It is a good argument for the terminal re-verification Step's premise: a narrow owner-surface run cannot see a budget it does not include.
