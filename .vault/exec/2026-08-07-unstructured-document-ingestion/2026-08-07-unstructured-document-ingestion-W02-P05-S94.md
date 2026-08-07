---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:1e2939f19fb8b701b2cad7fe66379b4e1c2ffc3adfcc4c9e7551b066b335711e'
step_id: 'S94'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Carry the printed currency code from the invoice draft through confirm into the ledger transaction so a foreign-currency invoice is recognisable as foreign rather than defaulting to euro, gated by a fixture invoice printing a non-euro code and an assertion that the stored transaction reports that currency, mutation-proven by dropping the carry and confirming the row is no longer distinguishable from a euro one

## Scope

- `src/cadrumo/application/ledger`

## Description

Semantic discovery found the carry already built end to end rather than absent:
the three structured-invoice parsers each read the document currency, the draft
model carries it, and the confirm boundary resolves operator override, then
document, then euro. Nothing needed writing on the production path. What was
missing was any observation of it: every bundled invoice fixture was
euro-denominated, so the euro-default branch and the carry branch were
indistinguishable in the suite.

- Add a non-euro structured fixture to the bundled evidence corpus with its
  provenance sidecar, denominated in Swedish kronor.
- Add a gate module driving parse through confirm on that fixture, asserting the
  persisted invoice reports the printed currency and not the euro default.
- Assert the operator override still outranks the document, so the carry was not
  implemented by ignoring the operator.
- Assert an unconverted foreign record reports no euro value rather than its
  face value, which is the over-declaration direction of the same defect.
- Thread a rate-provider seam through confirm, without which a foreign-currency
  confirm reaches the ECB Data Portal over the network and no test of this
  boundary could run offline.

## Outcome

A foreign-currency invoice is now observably foreign at the persisted record.
The gate distinguishes the three states that previously wore the same shape: a
euro invoice, a foreign invoice carried correctly, and a foreign invoice
silently defaulted to euro. Only the third is a defect, and nothing in the suite
could see it before.

The direction of error this watches is over-declaration. A kronor figure
recorded as euro overstates the base by roughly an order of magnitude, and the
gates in this tree are otherwise built against under-declaration.

## Verification

Cache posture: `-p no:cacheprovider`, serial `-n0`. Marker expression stated on
every invocation, because the default lane is `unit` and `integration` is
silently deselected otherwise.

    uv run --no-sync pytest src/cadrumo/application/invoices/tests/test_fx_conversion_provenance.py src/cadrumo/application/ledger/tests/test_evidence_foreign_currency_and_language.py -n0 -p no:cacheprovider -q -m "unit or integration"
    12 passed

Mutation proof, applied from outside the repository to the imported module
object under a lane-specific scratchpad filename, so nothing under `src` was
edited and no peer sweep could commit the mutation. An observable delta is
printed before the gate runs, so a fully green run cannot be mistaken for a
mutation that never landed.

    [MUTATION LANDED] drop_currency_carry: confirm now forces currency='EUR' regardless of the document
    3 failed, 9 passed, 1 warning in 21.15s

The red came from the property under test, not from fixture setup. The first
error line of the run reads:

    E   AssertionError: the currency was read from the document but lost at the confirm boundary: 'EUR'

## Notes

The Step row says "ledger transaction". The confirm path does not mint a
transaction; it mints a catalogue invoice record, which is where the currency is
persisted and where every downstream aggregation reads it. The gate is written
against the record that actually exists rather than the one the row names.

Building this uncovered a separate live defect, fixed here because it blocked
the Step outright: the confirm boundary offered no way to state the Modelo 349
clave, and the invoice writer refuses an intra-community supply that does not
carry one. Every intra-community invoice was therefore unconfirmable through the
evidence path, on any document in any language. The parameter and its CLI option
were added, with the help string set in all four locale catalogues.

The proof runs on the structured reader, which reaches no model. The text-layer
and vision readers carry the same currency field but could not be exercised: no
on-host reading model runs in this environment, and the campaign brief bars
loading one. Their currency carry is unproven and named here rather than
implied.
