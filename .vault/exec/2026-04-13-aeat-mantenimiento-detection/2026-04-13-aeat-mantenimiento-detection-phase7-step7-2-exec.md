---
tags:
  - "#exec"
  - "#aeat-mantenimiento-detection"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-aeat-mantenimiento-detection-plan]]"
---

# phase7-step7-2 env example alignment

## Intent

Mirror the new settings into `env/.env.example` so
`tests/test_config.py` stays green.

## Changes

- `env/.env.example` — new "Site-health detection (#95)" block with
  documenting comments for both variables.

## Acceptance

`tests/test_config.py` passes (verified in Phase 8 gates).

## Deviations

None.
