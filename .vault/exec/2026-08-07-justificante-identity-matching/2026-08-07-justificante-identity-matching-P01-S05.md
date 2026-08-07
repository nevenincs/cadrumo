---
tags:
  - '#exec'
  - '#justificante-identity-matching'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:beb879ed74c9a03834c2a0b19fd5155381428cb7a86ae8e59b67099110cd1a82'
step_id: 'S05'
related:
  - "[[2026-08-07-justificante-identity-matching-plan]]"
---

# Update the pinning test to the corrected signature and matching behavior, and remove the fixture's false expediente-as-presentation_id equivalence

## Scope

- `src/cadrumo/domain/justificante/tests/test_filing_target.py`

## Description

The parallel-authored pinning test HAD landed at HEAD:
`test_receipt_presentation_identifier_is_rejected_against_a_register_expediente_id`
in `test_filed_capture_calculation_history.py`, whose own docstring instructed a
reader to reverse it once the comparison was settled. It was absorbed in place,
not duplicated and not deleted. Two further tests blessed the same removed axis
and are recorded below.

## Outcome

In `test_filing_target.py`: replaced the fixture's expediente-shaped
`presentation_id` literal with a receipt-shaped Numero de justificante, removed
the `presentation_id` parametrize axis, and turned the two cases that asserted
rejection into cases asserting the receipt's own identifier is not consulted.
Added a test asserting the removal itself, carrying an anchor proving the same
call without the argument is accepted.

Absorbed the application-level pinning test into
`test_a_receipt_stamps_its_filing_even_though_its_identifier_is_not_the_register_expediente_id`,
keeping its divergence guard - the two identifiers must still differ, since that
is what makes the stamp evidence of anything. Reframed
`test_stamp_refuses_when_snapshot_expediente_disagrees_with_receipt_presentation_id`
into the positive statement, its genuine axis already being covered by the sibling
CSV test. Retargeted the mismatched-presentation-id row of the refused-metadata
case table onto the CSV axis, and removed
`test_filed_observation_capture_rejects_mismatched_presentation_id_before_stamping`,
whose premise no longer refuses and which would otherwise have duplicated the
reversed pinning test exactly.

## Verification

8 tests pass in `test_filing_target.py`; no assertion encodes the expediente id as
a valid presentation identifier and no test passes a keyword the predicate no
longer accepts.

## Notes

Each reversed test's docstring records what it previously pinned, so a later
reader sees a deliberate reversal rather than a weakened assertion.
