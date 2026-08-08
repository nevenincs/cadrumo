---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:825f6e4c5ec7f1203a104648e68e9bb0424f7c56f549d914d6daf46a71173dc7'
step_id: 'S189'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Description

- Add a typed, nullable `counterparty_identification_state` to the persisted transaction record beside `counterparty_eu_member_state`, registered in the JSON-boundary enum coercion.
- Add the same field to the persisted invoice record beside `counterparty_country`, with its own enum normaliser at the payload boundary.
- Populate it in the one invoice normaliser every structured creation path reaches, read terminally from the printed VAT number's own prefix; an explicitly supplied value wins.
- Re-key the aggregation art. 25 gate onto identification, renaming both of its reasons; the export arm keeps reading establishment because an export genuinely turns on place.
- Re-key the invoice-side base-routing screen the same way; its export arm likewise keeps the country.
- Re-key the invoice record's own intra-community guard, which read the address as a stand-in for the acquirer's registration.
- Update every fixture that had encoded the conflation, rather than leaving them pinning it.

## Outcome

Three sites read the address where Ley 37/1992 art. 25 reads the acquirer's VAT
identification: the aggregation gate, the invoice base-routing screen, and a
hard invariant on the invoice record itself. The third was found only because
the roundtrip fixture could not be constructed — it refused a
Spanish-established, French-identified acquirer outright, so that exemption was
unreachable rather than merely mis-gated.

Establishment and identification are now separate facts everywhere, and nothing
derives one from the other. Absent identification withholds the base with a
refusal naming the fact to record, and never falls back to the country.

Measured at HEAD before the change, both money directions were live: an
ES-established/DE-identified supply was refused
(`domestic_counterparty_on_intra_community_transaction`, over-declaration) and a
DE-established/ES-identified supply was accepted into casilla 59 with one
observation (silent under-declaration).

## Verification

    uv run --no-sync pytest src/cadrumo/domain/invoices src/cadrumo/application/aggregation -m unit -n0 -q --ignore=src/cadrumo/domain/invoices/tests/test_rate_coverage_versus_legality.py
    1 failed, 1039 passed, 11 deselected in 123.00s (0:02:03)

The one failure is `test_a_date_outside_the_rate_table_blames_the_year_not_the_rate`, and the ignored module is its sibling: a concurrent lane is mid-sweep renaming the rate-coverage predicate and editing the IVA rate table. Neither touches identification or establishment.

    uv run --no-sync pytest src/cadrumo/domain/invoices src/cadrumo/application/aggregation -m integration -n0 -q --ignore=src/cadrumo/domain/invoices/tests/test_rate_coverage_versus_legality.py
    11 passed, 1040 deselected in 298.02s (0:04:58)

Mutation proof, run from outside the repository as a plugin that reverts the gate to its establishment key. All three rungs asserted rather than assumed:

    PYTHONPATH=<scratch> uv run --no-sync pytest <the paired and sweep modules> -m unit -n0 -q -p s189_mut_rekey_to_establishment
    [MUT] plugin module imported (rung 1: banner)
    [MUT] rung 3 observable divergence confirmed: real=None mutated=domestic_identification_on_intra_community_transaction
    [MUT] rung 2: replacement gate invoked 11 times
    6 failed, 6 passed in 4.00s

Rung 3 is checked at import against the row the pair turns on, so a replacement
that happened to agree with the real gate would fail the plugin rather than
produce a green that proves nothing.

## Notes

The operator-supplied input for document-less paths is NOT landed. No CLI
option, command model or transaction-write path sets the new field, so a bank
row classified as an intra-community supply now refuses until the fact is
recorded. The refusal is fail-closed and names what to supply — it is not a
wrong number — but the workflow is blocked, and closing it is its own row.

The identification deriver is composed on the establishment authority, which
deliberately excludes the `ES` prefix because registration is not establishment.
Correct there, but it means a printed Spanish VAT number yields absent rather
than an affirmative Spanish identification. The effect is a refusal for the
weaker reason; no money moves either way, since both outcomes withhold the base.
Sharpening it belongs to the owner of that resolver.

Two sites outside this record's reach still read a country where the concept is
identification-flavoured: the counterparty tax-id normaliser routes a
non-Spanish VAT number through the Spanish validator whenever the ADDRESS says
Spain, and the same normaliser picks its IVA-number format from the address.
Neither moves money on its own, but both make a Spanish-established,
foreign-identified acquirer awkward to record.
