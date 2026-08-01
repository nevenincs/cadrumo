---
tags:
  - '#exec'
  - '#filing-period-casilla-channel'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:43d355358a1d2e333542c52356ee7d71d658b4ff3b191edde984c30e17eb2e96'
step_id: 'S06'
related:
  - "[[2026-08-01-filing-period-casilla-channel-plan]]"
---

# Update the two conditional-formula-trace tests refused by the typed text channel

## Scope

- `src/cadrumo/application/filing/tests/test_build_draft_conditional_formula_trace.py`

## Description

- Change the period casilla in the conditional-trace fixture from the quarter ordinal to the AEAT token.
- Record in the fixture docstring why the value is a string, so a later reader does not restore a Decimal.

## Outcome

Both conditional-formula-trace tests pass. They fail under the adopted routing change alone because the fixture fed a Decimal into a casilla the registry assigns to the typed string channel, and the typed channel correctly refuses a non-string.

These two were the only failures the dispatch brief anticipated. They were in fact two of twenty-two; the other twenty are recorded against S09.

## Notes

No assertion in either test was weakened to accommodate the change. The fixture value changed and the two structural assertions - trace-equals-declared-inputs, and draft reaches the filing-ready state with no divergence findings - are untouched.
