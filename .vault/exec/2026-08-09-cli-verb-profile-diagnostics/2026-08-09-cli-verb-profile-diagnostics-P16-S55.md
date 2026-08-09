---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:2e7cf62248175c1d6550e30a1e95ce76afce6dea7f568ff6a4ad940612caa683'
step_id: 'S55'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Repoint the date-binding guidance tests at the application helper and confirm the architecture budget gate is green

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_missing_date_binding_guidance_grounding.py`

## Description

- Added a test asserting the application helper, called directly with the addressing the transport builds, returns exactly what the transport returns.
- Ran the architecture boundary gate alongside the guidance tests.

## Outcome

The layer split is now a tested contract rather than an arrangement that happens to hold.

The added test is deliberately honest about its own limit, and says so in its docstring: it would still pass if the resolution migrated back into the CLI root, because it compares outputs rather than locations. What would fail in that case is the architecture budget gate, which is why the two are run together rather than the test being written to duplicate the gate's job badly.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_missing_date_binding_guidance_grounding.py src/cadrumo/entrypoints/cli/tests/test_architecture_boundaries.py -m "unit or integration" -n 0 -q
    10 passed in 26.02s

    uv run --no-sync pytest <owner surface> -m "unit or integration" -n 0 -q
    698 passed in 197.55s (0:03:17)

## Notes

The owner-surface run above now includes the architecture gate, which it did not before. That omission is what let the regression reach a campaign-wide run undetected.
