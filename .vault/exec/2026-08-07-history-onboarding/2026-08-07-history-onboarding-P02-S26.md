---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:572b8b28bfa9f42647157a01c8a6ef05c189155bf2f16c9849c02a6439fe3e90'
step_id: 'S26'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---
## Description

Two real justificante receipts parsed cleanly and agreed with their register rows
on modelo, ejercicio, period and taxpayer identity -- and still failed the match
predicate, because the receipt's embedded presentation identifier is not the same
string as the register row's expediente id, and production always feeds the
expediente id into the receipt's presentation-identifier comparison. The
consequence is that live justificante evidence never auto-stamps a filing record,
even for a period with a single filing.

That was only observable in production. This Step makes it reproducible in a
test. Existing coverage rejects a receipt-shaped identifier that has been
corrupted, which reads as a correct refusal of the wrong receipt; the fact here
is the opposite -- a REGISTER-shaped expediente id against a genuinely matching
receipt, rejected.

The predicate is deliberately not repaired. Which identifier the comparison
should use is still being established, and dropping the comparison would trade a
visible refusal for silent mis-stamping.

## Outcome

Added `test_receipt_presentation_identifier_is_rejected_against_a_register_expediente_id`
to `src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py`.

No new PDF fixture was authored. The synthetic Modelo 130 receipt already in the
tree carries a receipt-shaped presentation identifier, so pairing it with a
register-shaped expediente id reproduces the divergence exactly, with no new
specimen and no risk of a real receipt reaching a fixture.

The test first asserts the receipt agrees on every other axis when the
presentation identifier is not supplied -- that is what makes this a FALSE
rejection rather than an ordinary one -- then asserts the predicate returns
`False` with the register id supplied, and finally that the enrolment saves no
justificante, stamps no filing record, records no conflict, and leaves the filing
un-accepted with no external evidence.

Its docstring states the reversal condition: once the correct identifier is
settled, assert the receipt stamps and delete the rejection assertions.

## Verification

The test passes. Proven to bite by a runtime mutation that applies the tempting
"fix" -- the predicate stops comparing the presentation identifier altogether.
The test reds on `assert True is False`, naming the register expediente id in the
failure output.

## Notes

The mutation is the shape of the change this test exists to block, so its red is
the direct evidence that the pin holds against that specific edit rather than
against an arbitrary break.
