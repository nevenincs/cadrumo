---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:4caf96a65ea602f899f40f102e5735e3848614091304df1ecd7fd9c320f3b25a'
step_id: 'S206'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Description

- Pass the counterparty's established country into the ledger counterparty/category gate.
- Refuse an export or export-assimilated category whose counterparty is not POSITIVELY placed outside the Union, under its own new issue reason.
- Spare a country the bundled vocabulary does not carry, reading the same two authorities the ingestion path's declared-relief guard reads.
- Extract the allow/refuse decision into one named predicate, so the territory question and the catalogue-gap carve-out are stated once.
- Name the closed set of export categories, so the branch's two refusals cannot drift apart on membership.
- Classify the new reason in the ledger preflight totality mapping, and give it an operator-facing counterpart.
- Add the refusal sentence to all four locale catalogues.
- Correct two casilla-60 fixtures and one feed-parity fixture that asserted export routing from rows placing the counterparty nowhere.

## Outcome

The export branch demanded no evidence at all. It fired only when an EU member state was recorded, which made absence of a member state the sole signal of third-country establishment. Combined with the establishment field being unable to represent a third country, every unrecorded establishment reached the gate as the same blank a genuine export produced, and the supply was zero-rated.

Measured before and after, driven through real transactions rather than hand-supplied statuses:

    export, no country recorded    PASS  ->  REFUSE missing_counterparty_establishment_on_export
    export, XX / ZZ / QQ           PASS  ->  REFUSE missing_counterparty_establishment_on_export
    export to US                   PASS  ->  PASS
    export to US, EU VAT number    PASS  ->  PASS
    export to TH (uncatalogued)    PASS  ->  PASS
    export, DE established         REFUSE eu_member_state  ->  unchanged
    intra-community branch         unchanged in every case

Three conditions that wanted three different operator instructions are kept distinct rather than collapsed into one message: a wrong place says the category is wrong, no place says a fact is missing, and an uncatalogued place is not the operator's problem at all.

The uncatalogued carve-out is what separates a guard from a trap. A well-formed code naming a real jurisdiction the closed vocabulary does not list resolves to no territory, so refusing there would reject a legitimate export over a row nobody has written yet. A refusal an operator cannot act on teaches them to skip refusals, which costs more than the case it catches.

Two over-refusal directions were deliberately NOT built. Reading the counterparty's VAT identification here was rejected: a third-country company can hold a Member State VAT number, and the exemption turns on the goods leaving rather than on who registers the acquirer, so reading identification would be the identification-for-establishment substitution the intra-community branch exists to prevent, run backwards. Treating every unresolved country as suspect was likewise rejected, since the catalogue resolves for effectively every real counterparty.

Both this gate and the ingestion-path guard read one territory authority and one status authority, so there is a single answer to what evidence an export needs, consulted from two surfaces rather than two rules that can drift.

## Verification

    uv run --no-sync pytest src/cadrumo/application/aggregation/tests/test_export_demands_third_country_establishment.py -n0 -q -m unit
    18 passed in 5.23s

    uv run --no-sync pytest src/cadrumo/application/aggregation/tests src/cadrumo/application/ledger/tests src/cadrumo/domain/transactions/tests -n0 -q -m unit
    2272 tests ran; 37 were DESELECTED by -m 'unit' and never executed.
    2272 passed, 37 deselected, 16 warnings in 210.48s (0:03:30)

    uv run --no-sync ruff check src/cadrumo/application --output-format=concise
    All checks passed!

    uv run --no-sync python -m dev.locales scaffold --check
    ca.yml: ok
    en.yml: ok
    es.yml: ok
    hu.yml: ok

Both mutations were applied from outside the repository through a pytest plugin, leaving every tracked file untouched.

Reverting the export branch to its absence-means-third-country form: banner printed, holder rebound, 22 invocations, 9 red and 9 green. The nine that stayed green are the controls the old branch also handled correctly, which is the discrimination this Step adds.

Removing the uncatalogued carve-out: holder rebound, 15 invocations, red on exactly the two sparing cases and nothing else.

Every case drives the public gate with a constructed `Transaction` and lets the production code derive the territory and status itself. No case supplies a scope or status directly, so a green result cannot come from wiring that is dead.

## Notes

Adding the issue reason tripped the import-time totality guard in the ledger preflight, which refused to import until the member was classified. That is designed behaviour and it was classified as reaching preflight, never weakened.

A linter flagged the nested allow/refuse condition. Rather than flattening it and losing the reasoning, the decision was extracted into a named predicate carrying it in a docstring.

Three fixtures asserted export routing from rows recording no counterparty country. They encoded the defect as the contract, so they were corrected to record a genuine third country rather than worked around; their purpose, proving the base reaches the right casilla, is unchanged. One of them had the two feeds disagreeing on the very axis it exists to compare, with the invoice side placing the party in the US while the bank side placed it nowhere.

An earlier wide run reported failures in a concurrent lane's structured-country work and in one case here. Each pair of suites passed in isolation, and re-running the identical full selection returned all green, so the failures were a transient mid-write state in that lane rather than a defect. The reading was repeated before anything was attributed.

A sweeper committed the source and test changes before they could be committed from this lane; the landed content was verified against HEAD rather than inferred from a clean working copy.
