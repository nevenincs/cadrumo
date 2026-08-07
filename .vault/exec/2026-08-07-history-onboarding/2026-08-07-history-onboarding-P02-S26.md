---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:5ec17bf590701c6a30dca94ffbeb6c66d2fd1902b675506462757c2666dee51b'
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

THIS TEST HAS BEEN REVERSED, and that is the correct outcome rather than a lost
gate. The open question it was holding open got answered while this Step was
closing, and answered better than "correct the comparison": the presentation-
identifier parameter was removed from the predicate outright, on the ground that
AEAT's Numero de justificante and the register's expediente id are different
identifier namespaces and no receipt body ever carries the register value, so the
comparison could never agree and no caller could populate the parameter correctly.
The defect this Step made reproducible was therefore an incoherent axis, not a
mis-tuned one.

The test now asserts the reverse -- the divergent identifiers no longer block a
legitimate stamp -- and its divergence premise plus the do-not-tidy guard survive
into that reversal, because the divergence is what makes the stamp evidence that
the identifier is not consulted rather than evidence that two equal values agreed.

The residual risk this creates was the obvious thing to pin next and did NOT need
a new test from this Step: removing an identity axis means nothing in the receipt
distinguishes one filing of a period from another, which matters precisely because
a period can hold an original and an amendment. That gap is already covered by a
csv-based discrimination test asserting two same-period filings are told apart by
csv where the other axes cannot, plus two tests exercising the csv axis in both
directions. Adding a fourth would have duplicated an existing authority.
