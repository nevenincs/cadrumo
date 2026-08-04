---
tags:
  - '#exec'
  - '#profile-derived-selectors'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:f73ed5ec0f1b2ef938ad3f9586aedbd073840122b1624d7635ca934c8f04d2c4'
step_id: 'S11'
related:
  - "[[2026-08-04-profile-derived-selectors-plan]]"
---

# Replace the two year-gating frozensets and the hardcoded single-year gate with gating on registry content, dropping the minimo frozenset outright because its parameter-presence check already covers the same ground and keying the other two on consuming-binding presence, and land this in the SAME commit as the derived-scoped advisory because removing the code-maintained year ceiling is only safe once an uncovered year with a declared binding surfaces visibly rather than silently resolving to nothing

## Scope

- `src/cadrumo/application/modelo/_profile_binding.py`

## Description

## Outcome

The year ceilings are gone from code. A new filing year is now registry work alone -- bindings
and parameters -- with no constant to edit, which was the campaign's original complaint about
unbounded growth answered at its second source.

The minimo frozenset was dropped outright rather than replaced, because its parameter-presence
checks already covered the same ground from the registry. The other two now key on a declared
consuming binding, so the registry answers whether a year is covered.

This landed in the SAME commit as the advisory, and that coupling is the reason it is safe.
Removing a code-maintained year ceiling only becomes safe once an uncovered year surfaces
visibly rather than silently resolving to nothing. Landing them apart would have reopened the
exact silent-skip class this campaign exists to close -- a grounding pass caught that before
the Steps were dispatched, and the plan was rewritten to bind them together.

## Notes
