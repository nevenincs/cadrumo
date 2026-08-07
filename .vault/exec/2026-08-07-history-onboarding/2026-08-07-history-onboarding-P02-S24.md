---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:36865c666cff091e3a76bc3ba831b8920f212de70dba635d79a4eba5dba0adff'
step_id: 'S24'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---
## Description

Every declaraciones-register fixture in the tree rendered exactly one row per
period, so the assumption that a period maps to a single filing was
structurally untestable. A live authenticated read against the real register
returned six rows for one quarterly modelo and one filing year: four ordinary
quarters plus a SECOND third quarter and a SECOND fourth quarter, each with its
own expediente id, each presented months after the original, all registered
ALTA.

This Step encodes that shape as a synthetic fixture. Nothing was derived from
the real capture: the grid is hand-built from the STRUCTURE observed (row
multiplicity, distinct identifiers, distinct timestamps, populated request-type
cells) with invented identifiers, names and timestamps throughout. Class names,
column order and cell markup mirror the real sanitised capture already in the
tree so the parse exercises the same branches.

Ordinary single-filing periods sit alongside the duplicated ones deliberately,
so a consumer cannot satisfy the fixture by collapsing everything. No pager
section is present: whether the register ever paginates is unsettled and this
fixture makes no claim about it.

## Outcome

Files added:

- `src/cadrumo/tests/fixtures/aeat-sede/declaraciones-modelo-303-duplicated-period-synthetic.html`
- `src/cadrumo/tests/fixtures/aeat-sede/declaraciones-modelo-303-duplicated-period-synthetic.json`
- `src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_register_period_multiplicity.py`

The provenance sidecar declares `synthetic_generated` with the output digest and
byte size computed from the fixture's own bytes, matching the convention its
siblings in the same directory use.

Two tests read it. The first asserts the register read surfaces every rendered
row, that at least one period yields more than one, that at least one yields
exactly one, and that within a duplicated period the expediente ids and
presentation timestamps are all distinct. The second asserts the request-type
cell reaches the boundary record populated on every row and differs between the
earlier and later filing of a duplicated period. Every expectation is derived
from the fixture's own raw markup rather than hardcoded, so no tally is frozen
into the module and a regenerated fixture carries its assertions with it.

## Verification

`pytest src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_register_period_multiplicity.py`
passes.

Both gates were proven to bite by runtime mutation from a pytest plugin loaded
outside the repository, so nothing under `src` changed:

- Collapsing a period's filings inside the register read (routing its output
  through the history selector) reds the multiplicity test on `assert 4 == 6`
  against the fixture's own rendered-row count.
- Dropping the request-type cell from the parsed row reds the request-type test
  on `the register parse dropped the request-type cell`.

## Notes

The fixture's two request-type strings are plausible placeholders standing in
for a NON-EMPTY cell, which is the only property anything reads them for. AEAT's
verbatim vocabulary for that column is not established here and the test never
asserts either string literally.
