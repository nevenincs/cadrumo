---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:597963c516a745fb334fef31e15fd7e5a0df6c8208f929d8d4e805d94f20039e'
step_id: 'S44'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# replace the hardcoded 5-entry _GATING_FIELDS dict with a derivation from _MODELO_APPLICABILITY_RULES

## Scope

- `for each rule emit profile_key modelos message_key fix_command tuples covering income-categories entity-types estimation-regimes payer-facts`
- `the resulting projection must be a function not a dict so it stays in sync as rules evolve`
- `src/aeat/application/overview/__init__.py`

## Description

- Reconciled the derived applicability-gating projection to the Wave-2 review.
- Confirmed `acea52801e` supplied the reviewed implementation.
- Added this per-step execution record without changing production sources.

## Outcome

The 2026-05-29 review accepted the implementation. This record restores the one-Step, one-record traceability edge.

## Notes

The same reviewed commit also supports S43 and S46; each row receives its own record.
