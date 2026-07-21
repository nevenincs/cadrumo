---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S74'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# declare the modelo-151 calculation application-link surface in the registry (vaultspec-high-executor)

## Scope

- `src/aeat/_data/registry/aeat/modelos/151/`

## Description

- Rebaseline the M151 registry application-link surface.
- Confirm the current registry exposes the M151 calculation surface used by the live enrollment test.
- Close the stale-open registry-link row without changing source code.

## Outcome

Closed as current-code satisfied. The existing M151 registry surface supports the real two-year calculation enrollment.

## Notes

Verification: the focused W06/W07 stale-open test batch returned 42 passed.
