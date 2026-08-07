---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:d655b2f058b20141b863df1b6d9ac69e442d9c5e8d30a88188f7ea382349d56e'
step_id: 'S28'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---
## Description

Querying a modelo the taxpayer never filed returned zero rows cleanly against the
real register: no error, no failure row, a fully formed grid with nothing in it.
That outcome must stay distinguishable from the two shapes that genuinely are
failures -- a grid whose pager declares more records than it rendered, and markup
carrying no grid at all -- because an empty answer read as an error makes "you
filed nothing" indistinguishable from "the read broke".

The tree already carried an inline no-results shape, but it puts the sentence
inside a single-cell grid row, which exercises a different parse branch than the
markup the portal actually serves: the sentence lives in the grid's empty-body
section, which is not a row at all, so the row loop finds nothing to iterate
rather than finding a sentinel.

## Outcome

Files added:

- `src/cadrumo/tests/fixtures/aeat-sede/declaraciones-modelo-303-no-results-synthetic.html`
- `src/cadrumo/tests/fixtures/aeat-sede/declaraciones-modelo-303-no-results-synthetic.json`

The test lives in the module the sibling multiplicity Step introduced. The sidecar
declares `synthetic_generated` with the digest and byte size computed from the
fixture's own bytes.

`test_empty_register_grid_reads_as_a_complete_answer_not_a_short_one` asserts the
fixture renders zero rows, still carries the no-results sentence, and that the
sentence is NOT inside a grid row -- that last check is what keeps the fixture
from silently degenerating into the inline sentinel shape it exists to
distinguish. It then asserts the parse yields no rows, declares no record total,
reports itself not truncated, and that the register read returns the empty tuple
rather than raising.

## Verification

The test passes. Proven to bite by a runtime mutation that treats a row-less grid
as a short read. The register read then raises
`SedeParseError: ... rendered 0 row(s) but its pager declares None in total`,
which is precisely the confusion the test guards against.

## Notes

The fixture carries no pager section. Whether the register ever paginates is
unsettled and nothing here asserts either way.
