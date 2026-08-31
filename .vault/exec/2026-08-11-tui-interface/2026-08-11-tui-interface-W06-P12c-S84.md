---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:cdab1128d41b7ace18ffadc92ed6771df2cb472aed508a208eb6abe1871f75c1'
step_id: 'S84'
related:
  - "[[2026-08-11-tui-interface-plan]]"
  - "[[2026-08-11-tui-interface-W06-P12c-S83]]"
---

# Enroll verify only through its canonical validation capability and registered operation, and prove refused and unmeasured states, findings, terminal effect, typed refresh, focus return, and every supported geometry independently

## Scope

- `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_verify_action.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/modelo/action/verify.py`
- `A` `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_verify_action.py`
- `M` `src/cadrumo/application/modelo/operation_definitions.py`
- `verify:` `pytest test_c4_verify_action.py test_c4_rename_action.py test_c4_discard_action.py test_work_rename_operation.py test_lifecycle_operation_conformance.py` -> `104 passed`

## Notes

THE REPLAY-SAFETY PROPERTY IS WHAT DISTINGUISHES VERIFY, and it is now pinned.
The request carries the calculation revision and NOTHING TAXPAYER-SCOPED: the
profile the gates evaluate against is resolved at execution from live state. A
profile carried in the request would be frozen into the journal, and a replay
would produce a verdict that was true when submitted and is not true now -- on
the one surface whose job is telling an operator whether their filing is sound.
Asserted over the payload's WHOLE field set rather than by naming a suspect, so
a taxpayer-scoped field arriving later under any spelling fails here.

CANCELLATION IS COOPERATIVE, the opposite of discard, and read from the
operation rather than restated. Verification reads and reports, so abandoning
one part-way leaves nothing half-written -- which is exactly why discard, whose
operation declares cancellation UNSUPPORTED, must not offer the same
affordance. The two enrolments now pin their own halves of that contrast.

SUBJECT IS THE WORK UNIT WHILE THE PAYLOAD NAMES THE REVISION, and the two are
not interchangeable. Two verifications of different revisions of the same unit
must serialise, because they read the same evolving state; keying the subject
on the revision would let them run concurrently against a unit moving
underneath both.

A SYSTEMIC DEFECT, THE SAME CLASS AS W06.P12c.S82's AND FIXED DIFFERENTLY ON
PURPOSE. The blank-identifier proof failed on `"   "`: twelve identifier fields
in `operation_definitions.py` carry `Field(min_length=1)` with no whitespace
guard, so an all-whitespace id is journalled, takes a lease and is scheduled
before failing to resolve at execution -- real platform work for something that
can never settle.

The fix is NOT the one S82 used. A display name is STRIPPED, because that is
what the domain's own `_DisplayName` does. An identifier must NOT be stripped:
altering it changes what it addresses, so `" rev-1 "` and `"rev-1"` must stay
distinct. The guard is therefore `pattern=r"\S"`, which refuses `""` and
`"   "` while leaving an accepted value exactly as given. Applied to
`_WORK_UNIT_ID` and to verify's `calculation_revision_id` and `actor` -- the
identifiers these three enrolments actually submit.

THE REMAINING SIBLING FIELDS ARE A FINDING, NOT A SWEEP. Roughly nine further
identifier fields in that module share the looseness (`bucket_id`,
`verification_report_id`, `completeness_status`, further `actor` declarations).
They are recorded here rather than rewritten, because tightening a peer's
shared module wholesale on the strength of one enrolment's proof would change
validation for callers this row never examined.

CORRECTED IN MY OWN TEST: the field-set assertion originally named a
`request_version` field that does not exist. The measured set is
`{calculation_revision_id, actor}`.
