---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:a7e03da2bfab79a8c25e675eb01ed9a620e33f68fd41ff151b3c1dfbdf377e04'
step_id: 'S95'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Populate the euro equivalent at confirm for a foreign-currency invoice from a dated grounded rate carrying its source and rate date in the provenance envelope, refusing rather than inventing a rate when none is available for the invoice date, since a non-euro row with no euro equivalent is gated out of aggregation as unsupported currency and silently leaves the modelo totals, gated by a refusal test with a positive control proving a rated conversion reaches the casilla projection

## Scope

- `src/cadrumo/application/ledger`

## Description

Semantic discovery found the conversion policy already centralised and already
correct, so this Step completed it rather than building it. One stamp resolver
already decided which date a rate is taken at and when a record is deliberately
left unstamped, and a shipped singularity gate already refuses a second module
reaching a rate provider to decide it. Two things were missing: the stamp could
not say WHO quoted the rate, and none of it reached the operator.

- Add a typed conversion stamp carrying rate, rate date and source, replacing
  the bare pair the resolver returned.
- Add a rate-authority identifier to the exchange-rate provider protocol and
  implement it on the ECB reference-rate adapter, so a stamp names a published
  series rather than the anonymous fact that some provider answered.
- Stamp the source onto the persisted invoice record, at parity with the ledger
  transaction, which already carried rate provenance.
- Tighten the record conversion invariant from an all-or-nothing pair to an
  all-or-nothing triple.
- Expose the stamp and the euro projection of the totals on both operator
  surfaces, through the single shared field tuple both projections read.
- Reconcile every existing consumer of the stamp in the same change.

## Outcome

A euro figure on a foreign invoice now names the authority that produced it, or
there is no euro figure. The refusal half was already right and is now
observable: an unresolvable rate leaves the record unstamped, the euro accessors
report nothing, and the operator sees that state at confirm rather than
discovering later that the invoice quietly left the modelo totals.

Both directions of error are covered. The refusal gates watch under-declaration
by way of visibility. The face-value gate watches over-declaration, which
nothing else in this tree is aimed at: a foreign amount reported as euro
overstates the base the taxpayer is assessed on.

## Verification

Cache posture: `-p no:cacheprovider`, serial `-n0`. The marker expression is
stated on every invocation; the default lane is `unit` and `integration` is
silently deselected otherwise.

    uv run --no-sync pytest src/cadrumo/application/invoices/tests/test_fx_conversion_provenance.py src/cadrumo/application/ledger/tests/test_evidence_foreign_currency_and_language.py -n0 -p no:cacheprovider -m "unit or integration"
    collected 12 items
    12 passed in 10.01s

The conversion lane including the persistence roundtrip, the currency service
and the stamp singularity gate:

    uv run --no-sync pytest src/cadrumo/application/invoices/tests/test_fx_conversion_provenance.py src/cadrumo/application/ledger/tests/test_evidence_foreign_currency_and_language.py src/cadrumo/domain/invoices/tests/test_secure_storage_roundtrip.py src/cadrumo/domain/currency src/cadrumo/tests/test_fx_stamp_singularity.py -n0 -p no:cacheprovider -q -m "unit or integration"
    34 passed in 34.26s

Two mutation proofs, applied from outside the repository to the imported module
object under a lane-specific scratchpad filename, so nothing under `src` was
edited and no peer sweep could commit the mutation. Each prints an observable
delta before the gate runs, so a fully green run cannot be mistaken for a
mutation that never landed.

    [MUTATION LANDED] drop_fx_source: the stamp's source is the anonymous 'provider' again, not the ECB series
    1 failed, 11 passed in 29.54s

    [MUTATION LANDED] invent_a_rate: an unresolvable rate now silently becomes 1.0 -- the face value declared as euro
    3 failed, 9 passed in 65.89s

Both reds came from the property under test rather than from fixture setup. The
first error line of each run reads:

    E   AssertionError: a stored euro figure that cannot name its rate authority cannot be audited
    E   assert 'provider' == 'ecb_reference'

    E   AssertionError: assert Decimal('1') is None

The second is the one that matters. Inventing a rate made the euro base equal
the foreign face value, and the gate caught it as an amount rather than as a
shape.

The type checkers report zero diagnostics in any file this Step touched. The
repository total is peer churn in unrelated modules.

## Notes

The rate source is grounded but NOT bundled. The ECB reference-rate provider
resolves each observation from the ECB Data Portal at lookup time over the
network, and no offline rate corpus ships in the tree. That changes what the
refusal means in practice: with no network, confirming a foreign-currency
invoice raises a transport error rather than resolving a rate.

That is still a refusal and never an invention, and the split between the two
failure modes is deliberate. An unresolvable rate leaves the record unstamped
and visibly unconverted, which an operator can see and correct. An unreachable
rate SOURCE raises, because a silent unstamped record there would let an outage
quietly remove invoices from the modelo totals. Neither path produces a number.

Whether a bundled offline rate corpus should ship is a decision above this Step.
It is flagged, not taken.

Confirming a foreign invoice previously had no way to avoid the network at all,
which is why no test of this boundary could exist. A rate-provider seam was
added to the confirm path for that reason; production still defaults to the ECB
adapter.
