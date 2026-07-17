---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-06-26'
modified: '2026-07-17'
step_id: 'S20'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

# Verify W03.P06 no-shift: run pytest --collect-only -q clean and assert the prefill modules retain distinct names and tiers with no merge and no behaviour change (docstring-only clarification)

## Scope

- `src/aeat/application/calculations/tests`

## Description

- Assert the three prefill modules retain distinct names and tiers with no merge: the relation resolver in the relation prefill module, the `previous_filing` carry in the binding prefill module, and the `aeat_prefilled` flag in the registry schema.
- Run the application calculations test suite.

## Outcome

W03.P06 no-shift proven. The three prefill tiers remain distinct (the relation prefill module owns the relation resolver, the binding prefill module carries 16 `previous_filing` references, and the registry schema owns the `aeat_prefilled` flag), with no merge and no behaviour change (docstring/comment-only clarification). The application calculations test suite ran 401 passed.

## Notes

None.
