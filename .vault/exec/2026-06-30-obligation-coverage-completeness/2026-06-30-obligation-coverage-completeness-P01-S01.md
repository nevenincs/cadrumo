---
tags:
  - '#exec'
  - '#obligation-coverage-completeness'
date: '2026-07-01'
modified: '2026-07-01'
step_id: 'S01'
related:
  - "[[2026-06-30-obligation-coverage-completeness-plan]]"
---

# Add the OUT_OF_SCOPE_OBLIGATIONS central declaration

## Scope

- `src/aeat/core/_modelo.py`.`
- `src/aeat/core/_modelo.py`

## Description

- Add `OUT_OF_SCOPE_OBLIGATIONS`, a central typed mapping of registry modelo to
  recorded product-scope reason, beside `NON_REGISTRY_MODELOS` in the core modelo
  module.
- Declare the four initial out-of-scope modelos (`036`, `151`, `714`, `840`) with
  a reason each, per the ADR Decision 4 dispositions.
- Re-export the constant from the core package `__init__`.

## Outcome

The central declaration is the sole home of the "explicitly out of scope" bucket,
so an invisible modelo is always a recorded decision, never a silent omission.
Core modelo parity tests stay green (4 passed).

## Notes
