---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:ecbef5364cf10175423f03f243aade84f19fcb2481837d1bb541f066c8114f79'
step_id: 'S27'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium close the third profile-fact write door and correct the write-door docstring that asserts a single-door invariant the tree does not hold

## Scope

- `src/cadrumo/application/user_profile/_cotejo_apply.py and src/cadrumo/application/wizard/_persistence.py`

## Description

- Enumerate by measurement which doors reach the fact-change authority, before
  changing any of them.
- Judge censal-adopted facts against the profile schema, with completeness
  following the record's setup state rather than hardcoded.
- Correct the docstring asserting a single door, and the caller enumeration that
  would have become false with this change.

## Outcome

The door is hardened, and the ruling is grounded rather than reflexive: an
accepted decision already holds that the user-profile schema is a CONTRACT and
the code is brought to it, and names this exact instance as unclosed. The
reasoning recorded in the code is that an official ORIGIN is not evidence about
either question the schema asks -- the authority certifies what the taxpayer's
censal situation is, not that a value belongs at a path this application
declares nor that it arrives in the shape that path is typed. Provenance is
untouched: each adopted fact keeps its artefact token, so a certified value is
still distinguishable from a typed one.

Completeness follows the record's setup state rather than being demanded
outright. That distinction was found by measurement, not assumed: running a real
censal fact set through the validator produced zero shape or path errors and
three missing-required-field errors, and the reconciliation runs DURING setup,
so a hardcoded completeness demand would have refused every mid-setup
reconciliation.

The docstring half was the more insidious defect. It claimed to be the one door
onto profile facts -- untrue when written, and precisely the prose that invited a
second unjudged write. It now says what is true: not one door, but one judge.

Verified independently: 4 passed. The two bite proofs bite in OPPOSITE
directions -- reverting the door to unjudged reds two tests, over-hardening it to
demand completeness reds one -- which is what demonstrates the tests pin the
correct middle rather than rewarding strictness.

## Notes

The symptom that motivated this row, a censal filing date written to an
undeclared path, was already gone from the tree; the hole that admitted it was
not. Fixing the symptom without the hole is what left this open.

Two defects surfaced and were deliberately not acted on. A fourth state-changing
door promotes a record to COMPLETE setup state without validating it, which is
the same defect class and arguably more serious because filing readiness keys off
that state. And a production `assert` sits on a filing-adjacent write path, which
is stripped under optimised interpretation and is an uninstructive crash if it
ever reaches an operator. Both are carried as their own rows.

A functional test driving this path could not run: an entire command-line test
package was dark on a circular import in the storage facade, from in-flight lazy
conversion work. The risk it covers was addressed directly with a fourth test
rather than left uncovered.
