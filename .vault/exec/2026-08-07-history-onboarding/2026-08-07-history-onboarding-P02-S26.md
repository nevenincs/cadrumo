---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:e23b288c4e4b3239769cbaf9926e6cb5407cad121f4fc524e7500fe4ae63f7bd'
step_id: 'S26'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---
## Description

Two real justificante receipts parsed cleanly and agreed with their register rows
on modelo, ejercicio, period and taxpayer identity -- and still failed the match
predicate, because the receipt's embedded presentation identifier is not the same
string as the register row's expediente id, and production always feeds the
expediente id into the receipt's presentation-identifier comparison. So live
justificante evidence never auto-stamps a filing record, even for a period with a
single filing.

That was only observable in production. This Step makes it reproducible.
Existing coverage rejects a receipt-shaped identifier that has been corrupted,
which reads as a correct refusal of the wrong receipt; the fact here is the
opposite -- a REGISTER-shaped expediente id against a genuinely matching receipt,
rejected.

The predicate is deliberately not repaired. Which identifier the comparison should
use is still being established, and dropping the comparison would trade a visible
refusal for silent mis-stamping.

## Outcome

Added `test_receipt_presentation_identifier_is_rejected_against_a_register_expediente_id`
to `src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py`.

No new PDF fixture was authored. The synthetic Modelo 130 receipt already in the
tree carries a receipt-shaped presentation identifier, so pairing it with a
register-shaped expediente id reproduces the divergence with no new specimen.

The other Modelo 303 receipt fixtures were evaluated and rejected for this use on
measurement, not preference: their sidecars declare synthetic provenance, their
CSV is a placeholder token, and their parsed presentation identifier is absent
entirely. The predicate short-circuits its presentation check when the receipt
states no identifier, so such a receipt would MATCH -- silently inverting this
test's meaning rather than exercising it.

The identifiers are shaped to the boundary they exercise. The register id is 16
characters as `<year><sequence><checksum-letter>`, satisfying the sede pattern and
sitting inside both the declared 12-32 bounds and the narrower observed 14-20
range; the receipt CSV is 16 uppercase alphanumeric, satisfying the strictest
checker rather than depending on the loosest type. Register and receipt
identifiers differ in LENGTH as well as value, so the divergence is visible at a
glance.

The test asserts the receipt agrees on every other axis when the presentation
identifier is not supplied -- that is what makes the rejection FALSE rather than
ordinary -- then that the predicate returns false with the register id supplied,
and finally that enrolment saves no justificante, stamps no record, reports no
conflict, and leaves the filing un-accepted with no evidence.

A guard refuses the tempting cleanup of making the two identifiers agree, which
would silently turn this into a test that a matching receipt matches. It compares
case-folded, the way the predicate itself normalises, so a case-variant of the
same identifier cannot slip past a naive inequality -- a case the obvious
implementation of that guard would miss.

## Verification

The test passes. Proven to bite by a runtime mutation applying the tempting fix:
the predicate stops comparing the presentation identifier at all. Red observed:
`assert True is False`, naming the register expediente id.

Re-run explicitly serialised with `-n0` after the project default was found to
inject `-n auto --dist=loadfile`: verdict unchanged, still red. Unmutated control
green.

## Notes

The mutation is the exact shape of the change this test exists to block, so its
red is direct evidence the pin holds against that edit rather than against an
arbitrary break.
