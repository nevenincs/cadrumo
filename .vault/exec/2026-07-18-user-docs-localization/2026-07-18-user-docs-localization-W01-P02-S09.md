---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-19'
step_id: 'S09'
related:
  - "[[2026-07-18-user-docs-localization-plan]]"
---

# Enroll the localization gates in the docs-check lane under the docs marker and confirm the lane runs them

## Scope

- `justfile`
- `dev/docs/tests`

## Description

- Confirm the docs-check lane enrolls the localization gates: the lane already globs the `dev/docs/tests` directory and filters by the `docs` marker, and the new gates carry that marker.
- Run `pytest --collect-only` under the exact docs-check invocation to verify collection.

## Outcome

The exact docs-check collection surfaces every new gate: the completeness parametrization, the parity gate, and the per-language build matrix. No justfile change was required because the lane globs the test directory and the gates carry the `docs` marker. `pytest --collect-only -q dev/docs/tests` is clean.

## Notes

The docs-check lane is now expected red until the translation wave lands, driven solely by the completeness gate. Every other gate the wave touched is green.
