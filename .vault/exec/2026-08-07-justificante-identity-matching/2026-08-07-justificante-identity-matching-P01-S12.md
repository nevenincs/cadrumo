---
tags:
  - '#exec'
  - '#justificante-identity-matching'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:07dd021e0cd22555bcde7ada49a8babef7ef4f61ea2dd8142b4277f0accdec66'
step_id: 'S12'
related:
  - "[[2026-08-07-justificante-identity-matching-plan]]"
---

# Add a mutation-proof test proving the new csv defense-in-depth check discriminates two same-period filings sharing modelo, ejercicio, period and tax_id, confirming a wrong-artefact-selection bug would be caught even though the row-scoped fetch is the primary binding

## Scope

- `src/cadrumo/application/live/tests`

## Description

The hazard is two filings for one period sharing modelo, ejercicio, period and
tax_id - every axis the narrowed predicate consults - which is the case real AEAT
data produced.

## Outcome

Added
`test_the_csv_check_tells_two_same_period_filings_apart_where_the_other_axes_cannot`.
It first asserts the predicate accepts the same receipt for BOTH filings, which is
what makes the CSV axis load-bearing rather than redundant. It then enrolls the
same receipt bytes against two register rows differing only in expediente id: the
row whose artefact URL names the CSV printed on those bytes stamps its filing, and
the row whose URL names the other filing's CSV is refused with its filing left
unstamped. No new fixture bytes were needed.

This models the bug class the ADR names - a storage or selection defect
re-associating a correctly fetched artefact with the wrong observation after
capture - rather than an AEAT round-trip failure.

## Verification

Gate proven to bite: an out-of-repo `-p` plugin replaced the CSV reader with a
value that agrees with whatever it is compared against, leaving the comparison
running but unable to fail. Run with `-n0` explicitly, this test went red. The
same test was also run under the project's default addopts and went red there too,
because a `-p` plugin on `PYTHONPATH` is loaded by xdist workers as well; `-n0`
was passed for the canonical proof regardless, and both readings are recorded.

## Notes

The check is defense-in-depth. The primary protection against cross-filing
mis-pairing is the row-scoped fetch hardened in S13, and the test docstring says
so rather than overstating what the CSV comparison guarantees.
