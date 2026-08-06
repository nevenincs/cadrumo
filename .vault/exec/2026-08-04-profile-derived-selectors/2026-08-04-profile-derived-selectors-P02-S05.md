---
tags:
  - '#exec'
  - '#profile-derived-selectors'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:87580a3e86b3baaba994e81a1afd6f222a96831d9c5c7533edba75a1f3d77a08'
step_id: 'S05'
related:
  - "[[2026-08-04-profile-derived-selectors-plan]]"
---

# Consume the helper as the FIRST statement of the per-fact validation, before the field-index lookup, not merely before the unknown-path arm, because during this phase the declarations still stand so the index lookup succeeds and the unknown-path arm never fires, and invert in the same commit the write-door half of the override proof from P01.S01, whose fixture writes a sentinel through the real write door and will begin raising the moment this refusal lands

## Scope

- `src/cadrumo/application/user_profile/_validation.py`
- `src/cadrumo/application/modelo/tests/test_derived_aggregate_override_real_path.py`

## Description

## Outcome

The write door refuses every value at a declared derived path, including a clear, and the
refusal names the surface that edits the real source facts rather than merely rejecting.

The placement is the load-bearing detail and it is the one most likely to have shipped green
and useless. The check is the FIRST statement of the per-fact validation, before the
field-index lookup -- not merely before the unknown-path arm, which is how the Step originally
read. While the per-year declarations still stood that lookup SUCCEEDED, so the unknown-path
arm never fired and control fell through to the type checks, which accepted the write. A check
placed after the lookup would never have run. A grounding pass caught this before an executor
reached the Step.

It is judged beside the unknown-path check rather than through the value-refusal authority.
That authority is value-scoped against a field declaration and expressly declines to judge
absence; this refuses every value and must keep answering once the declarations are gone. Its
kind enum and both exhaustive consumers are byte-unchanged.

The message is a plain formatted string, not a locale key, and that was a deliberate reversal
of the Step as written. Every sibling issue message in that module is a formatted string --
the translator is not imported there at all. Introducing a locale key for this one message
would have been the inconsistent pattern rather than the consistent one, so the locale Step
was re-scoped rather than executed against a module that is not locale-backed.

Proved four ways at the boundary: a derived aggregate path refuses, a legitimate
per-descendant fact does not, a kept operator field does not, and the guarderia path refuses
too.

The write-door half of the override proof inverted in the same commit, since the refusal is
what breaks it. It now pins the refusal and asserts storage as well as the raise, because a
refusal that still let the value through would leave the calculation override open while
looking closed.

## Notes
