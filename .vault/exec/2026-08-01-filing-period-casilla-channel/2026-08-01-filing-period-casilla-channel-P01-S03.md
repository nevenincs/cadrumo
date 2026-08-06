---
tags:
  - '#exec'
  - '#filing-period-casilla-channel'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:8eabbae8ece6f5f81702047b9e409f1000eb928d750727445f34b55692617bfc'
step_id: 'S03'
related:
  - "[[2026-08-01-filing-period-casilla-channel-plan]]"
---

# Thread the resolved period token through the engine text_inputs channel so it persists in input_values_by_casilla_id

## Scope

- `src/cadrumo/application/modelo/_calculation_resolution.py`

## Description

- Change the calculation input resolver to return a frozen `ResolvedCalculationInputs` carrying both typed channels, rather than a bare Decimal mapping.
- Accept an optional caller-supplied text overlay and merge it over the declaration-derived token, matching the precedence the Decimal channel already uses.
- Update both call sites - the trusted-mesh calculate path and the source-staging materialiser - to read the two channels rather than reconstructing one.

## Outcome

The token now reaches the engine's string input channel and merges into the persisted string replay mapping, which is where every typed text casilla already lives. No persisted model shape changed: the computed Decimal mapping and the observation value stay strictly Decimal, so there is no version bump, no upgrader and no migration surface.

Returning both channels together is a deliberate design choice rather than a convenience. A bare-Decimal return lets a caller forget the string channel and lose a text casilla in silence - structurally the same failure as the literal membership filter this phase retired, one layer further out. Handing the caller both channels makes the omission impossible to express.

The taxation-comparison caller reads only the Decimal channel, which is correct: that surface runs Modelo 100 exclusively and no Modelo 100 revision declares the `filing_period` role. That was confirmed against the registry rather than assumed, and the reason is recorded at the call site so a later reader does not mistake it for a dropped channel.

## Notes

The comparison surface has no string input channel at all, so had a Modelo 100 revision declared the role, this change would have dropped it. It does not, and the inline note at the call site says so explicitly, but a future revision adding the role to Modelo 100 would need that surface widened.
