---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:e0df7c30118785d6fd6f1e8a29a8d0f865c13f5e377efc6fd29ffc343dcd1969'
step_id: 'S54'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Reduce the CLI root to a thin call into that application helper, restoring the zero registry-authority-read budget

## Scope

- `src/cadrumo/entrypoints/cli/_modelo.py`

## Description

- Replaced the in-module resolution with a delegation: address the work unit, call the application helper, fall back to the binding id.
- Confirmed the module now contains zero occurrences of the authority-read expression the gate counts.

## Outcome

The CLI root is a transport again, and the architecture budget is satisfied at its intended value rather than by relaxing it.

    rg -c 'resources\(\)\.modelos\.authority' src/cadrumo/entrypoints/cli/_modelo.py
    0

Behaviour is unchanged: the same guidance text is produced for the same inputs, and the same fallback applies. Only where the resolution runs moved.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_missing_date_binding_guidance_grounding.py src/cadrumo/entrypoints/cli/tests/test_architecture_boundaries.py -m "unit or integration" -n 0 -q
    10 passed in 26.02s

The architecture gate that failed with `assert 2 <= 0` before this Step now passes.

## Notes

The fallback stayed at the transport rather than moving with the resolution, because the caller's contract is "always return something renderable" while the helper's is "return what resolved, or nothing". Keeping those separate is what lets the helper report honestly that it found nothing.
