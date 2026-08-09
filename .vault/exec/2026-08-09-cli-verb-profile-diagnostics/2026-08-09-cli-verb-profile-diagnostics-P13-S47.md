---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:60022d903bac6c115190aea3244f0a4fd31e959c4c3b7ef7372c7ef31ce0f952'
step_id: 'S47'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Route the date-binding calculate guidance through the path-based renderer

## Scope

- `src/cadrumo/entrypoints/cli/_modelo.py`

## Description

- Switched this site from the selector renderer to the path renderer, since the keys it holds come from registry bindings and are schema paths.

## Outcome

The site now renders a real operator label where the field resolves, instead of passing the raw profile key through untouched.

This is a correction to work recorded as delivered earlier in this campaign. The original wiring produced no error, no warning and no test failure - it simply resolved nothing, which is precisely why it survived review.

A key that names no schema field, such as a derived-selector pattern expanded for a filing year, still renders as itself. That is correct: there is no label to show for it, and inventing one would be worse than showing the key.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_missing_date_binding_guidance_grounding.py src/cadrumo/entrypoints/cli/tests/test_modelo_requires_profile_grounding.py src/cadrumo/entrypoints/cli/tests/test_modelo_requires_data_inventory.py src/cadrumo/application/modelo/tests/test_data_inventory_profile_keys.py -m "unit or integration" -n 0 -q
    10 passed, 1 skipped in 12.10s

That run predates the final test correction; the skip it reports was in the date-binding test's own label derivation, which still used the selector lookup, and is gone in the run recorded under the sibling test Step.

## Notes

No locale change was needed: both messages already interpolate a rendered value, and only the rendering changed.
