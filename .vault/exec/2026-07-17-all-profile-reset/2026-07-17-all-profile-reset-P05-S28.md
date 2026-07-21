---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S28'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---




# Migrate the four locale catalogues for the reset and sandbox families through the locales CLI

## Scope

- `src/cadrumo/locales/en.yml`

## Description

- Through the locales manager (the same code path the `set`/`remove`/`scaffold` CLI verbs use), scaffold the three new `cli.operator_surface.help.config.reset_{start,status,resume}` keys into all four catalogues and set each locale's value from the already-translated `cli.config.reset.*_help` copy.
- Remove the orphaned `cli.config.profile.sandbox.use_help` / `use_name_help` leaves from all four catalogues (the `sandbox use` verb was deleted in S19).

## Outcome

`scaffold --check` reports ok for en/es/ca/hu; the reset CLI verb keys were already present from S26/S21. Parity, translation-honesty, and coverage-inventory gates green (35 passed). The catalogues were edited only through the manager API, never by hand.

## Notes

Routed the `set` values through the manager in-process (reading the existing translated verb-help strings) rather than passing accented es/ca/hu text as shell argv, avoiding console-encoding corruption while staying on the sanctioned CLI code path.
