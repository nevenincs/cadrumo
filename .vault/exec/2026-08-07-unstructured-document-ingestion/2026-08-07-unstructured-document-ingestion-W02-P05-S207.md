---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:93a75182d4c0d3d5eca42189bc40991f1c401c6a6753e5845b69d720e4b21229'
step_id: 'S207'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Refuse a DECLARED category that presupposes an establishment the classification assembly recorded as a gap, since when the rule table returns nothing the document's own UNTDID code is taken as DECLARED and the rate-tier contradiction check is by its own docstring silent on every non-domestic category including export. So a document asserting an export code routes an unresolved counterparty straight to a zero-rated category. The chain is incomplete at HEAD and completes when the concurrent ingestion-category resolver lands, which is why it is rowed now rather than after

## Scope

- `src/cadrumo/application/ledger`

## Description

- Add the `UNSUPPORTED_RELIEF` outcome to the core resolution axis, distinct
  from the contradicted one because nothing disagrees.
- Add the named set of declared categories whose whole legal basis is where the
  counterparty is established, and the predicate that refuses one when the
  assembly recorded a residency as a gap.
- Ask the predicate BEFORE the tier check and before the verdict comparison, so
  it fires on the one shape that passes every other rung.
- Carry the counterparty's printed country status into the resolution from the
  confirm path, through the shipped status axis rather than a second reading.
- Author a UBL fixture declaring the export code while printing no country, and
  its provenance sidecar.
- Add the guard's tests, both directions, plus the end-to-end withholding proof.

## Outcome

The row's premise reproduced exactly. Two declared codes relieve a supply of
Spanish output IVA purely on where the counterparty is -- an entrega
intracomunitaria under LIVA art. 25 and an export under art. 21 -- and both
passed every existing rung by construction. The tier corroboration is silent on
every non-domestic category, documented as such on its own docstring, and there
is no rule-table verdict to disagree with precisely BECAUSE the establishment is
missing. So an unplaceable counterparty reached a zero-rated category with
nothing objecting anywhere.

The category is withheld, and the document is NOT called wrong. Absent
establishment does not disprove the claim: the paper may be entirely correct and
the evidence simply does not reach it. That is why this is its own outcome
rather than a contradiction -- a contradiction sends an operator to decide which
half to believe, this sends them to supply the establishment, and collapsing
them would send them to re-read a page that was never the problem.

The set is narrow and every exclusion is a decision rather than an oversight.
The domestic members presuppose Spanish establishment, which the tier
corroboration already checks. A domestic reverse charge also prints no cuota,
but it OBLIGES the recipient to self-assess output IVA, so mis-honouring it
over-declares rather than under-declares and is not this hazard; a guard widened
to every zero-cuota code would withhold exactly the reverse-charge treatment the
preceding slice exists to preserve.

**The false-positive direction was designed for, not merely tested afterwards.**
The scope resolver answers from a closed vocabulary, so a well-formed code naming
a real jurisdiction it does not list resolves to nothing and the establishment is
recorded as a gap -- while the document said perfectly clearly where the party
is. Measured, `TH` is exactly this. Refusing there would reject a legitimate
Thai export because of a row nobody has written, which is the false positive
that teaches an operator to stop reading refusals. Only an absent, malformed or
ISO-unassigned code reaches the refusal, and each of those genuinely established
nothing. The sparing is keyed on the shipped three-way status axis rather than on
a second reading of the same evidence.

Three premises the dispatch carried were re-measured before building, and one
was false. The Facturae parser assigns no category at all: the two assignment
sites are the CII and UBL branches, so the fixture is UBL. `TH` resolves
uncatalogued rather than third-country, so unresolved is not the complement of
third country. And the vocabulary does carry most third countries -- US, GB, CH,
JP, CN, MA, BR, IN, AU, NO, TR, CA, MX, AR and ZA all resolve -- so the
uncatalogued case is a narrow exemption rather than the common path, which is
what makes the guard worth having at all.

## Verification

    uv run --no-sync pytest src/cadrumo/domain/iva/tests src/cadrumo/application/ledger/tests src/cadrumo/tests/test_iva_category_singularity.py -n0 -q -m unit
    1854 passed, 21 deselected, 16 warnings in 202.62s (0:03:22)

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_ingestion_category_resolution.py -n0 -q -m unit
    25 passed in 5.24s

The end-to-end proof runs the authored UBL document through the real reader and
the real confirm, and asserts on the PERSISTED record rather than on the
resolution, because the record is what a filing is built from: a withholding
that stopped short of the catalogue would satisfy an internal check and change
no declaration. It carries a positive control asserting the reader still emits
the export code, without which the category would be absent for an entirely
different reason and the test would pass proving nothing.

The vocabulary-sparing test carries the same shape: the spared claim is asserted
beside the identical claim with no country printed, which must still refuse. A
sparing test alone cannot distinguish a working exemption from an inert guard.

## Notes

The guard's population includes legitimate intra-community supplies whose
documents omit a country. The bundled German intra-community fixture is exactly
that: it declares the intra-community code and prints no country for either
party, so its category is now withheld. That is doctrinally right here -- a
printed VAT number establishes identification and never establishment, which is
the split this apparatus exists to hold -- but it means real, correct documents
now reach the record with no treatment and no explanation an operator can see.

That consequence lands on the visibility gap reported separately and not closed
by this slice: nothing in production reads the resolution or the review items on
the confirmation result, so an operator meeting a blank category cannot learn
why it is blank. The withholding is the right behaviour and the silence is not.
Until a surface carries the outcome, this guard trades a silent wrong value for
a silent absent one, which is the better trade and is still not the right end
state.

A sibling lane authored CII export fixtures in the same corpus directory while
this ran. They were left uncommitted and out of this commit's pathspec.
