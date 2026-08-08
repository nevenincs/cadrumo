---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:df84a8d62a4567ea732e8cee21c2d598730b9026345584e7f727b54c41cac95e'
step_id: 'S153'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Description

- Add an `alpha3` column to the bundled printed-country vocabulary, one code per record for all 58 countries, with a header block stating why the correspondence is registry data rather than a literal in the feature module that needed it.
- Extend the vocabulary loader with an alpha-3 index and three refusals: a record carrying no alpha-3 code, two records claiming one alpha-3, and one alpha-2 stating two alpha-3s.
- Add `country_code_for_stated_country_code` to the IVA domain, resolving a structured record's country element from either code system onto the one alpha-2 form, and promote it to the package facade.
- Read the country element in the Facturae and UBL parsers, carried verbatim in whichever system the format states, and leave the Cross Industry Invoice branch unread.
- Resolve the stated code to alpha-2 at the structured draft boundary, carry it on both party sides of the draft and of the counterparty side selector, and route it into the establishment ladder's country rung.
- Ground the derived value against the form the record states rather than against itself, by giving the structured grounding entry point the explicit anchor its printed siblings already accept.
- Surface both party country codes on the operator-facing extract payload and populate them off-default in the provenance roundtrip fixture.
- Replace the reachability gate asserting the structured parsers supply no country with one asserting they now do, and add a gate keeping the remaining Cross Industry Invoice gap visible.

## Outcome

The Spanish national format resolves a counterparty territory end to end for the first time. A Facturae invoice states its country in ISO alpha-3 inside the same address block whose postal code was already being read, so the evidence was present and parsed while establishing nothing: handed to the alpha-2 resolver it failed a length check and returned the same value a document stating no country returns. That failure had no signal of any kind, and it shut the postal rung for the whole format.

The correspondence closing it is a column beside the alpha-2 code it names, so both code systems and every printed country name now resolve in one reviewable table, and the loader refuses a table that could load a contradiction rather than resolving a country by file ordering.

Two rulings carried in the dispatch were tested and one did not survive. The expectation was that a translated value would arrive `UNANCHORED` for free, distinguishing a stated code from a derived one at no cost. It does not: the anchor search is boundary-aware only at NUMERIC edges, so `ES` is an ordinary substring of `ESP` and matches it. An implementation grounding the resolved value would therefore have reported a false anchor on an accidental substring hit, pointing an operator at nothing. The honest mechanism was already documented on the provenance envelope, whose anchor field means the source form a value was read from and already carries `1.234,56 EUR` for the value `1234.56`. So the country grounds against the form the record states, `ESP` for Facturae and `ES` for UBL, and the derivation is visible in the anchor differing from the value rather than in a grounding outcome the mechanism does not draw.

The Cross Industry Invoice branch is deliberately untouched and its gap is now gated rather than remembered.

## Verification

Semantic discovery ran before any edit and established that no alpha-3 correspondence existed anywhere in the tree; the only country-code maps found were the VAT-prefix ones, a different axis.

    uv run --no-sync vaultspec-rag search "read the party country code from a structured e-invoice" --type code --port 8766 --timeout 120
    uv run --no-sync vaultspec-rag search "map an ISO alpha-3 country code to its alpha-2 form" --type code --port 8766 --timeout 120

The two new suites, driving the real encrypted evidence service and the real draft extraction:

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_structured_path_country_codes.py -n0 -q -p no:randomly
    12 passed in 4.31s

    uv run --no-sync pytest src/cadrumo/domain/iva/tests/test_stated_country_code.py src/cadrumo/domain/iva/tests/test_printed_country_name.py -n0 -q -p no:randomly
    99 passed in 0.85s

Both marker lanes over the affected packages, sequential:

    uv run --no-sync pytest src/cadrumo/domain/iva src/cadrumo/application/ledger src/cadrumo/adapters/inbound/einvoice src/cadrumo/tests -n0 -p no:randomly -m "integration and not external_tool and not os_keychain and not resident_service" -q
    24 passed, 3126 deselected in 89.22s

    uv run --no-sync pytest src/cadrumo/domain/iva src/cadrumo/application/ledger src/cadrumo/adapters/inbound/einvoice -n0 -p no:randomly -m "unit and not external_tool and not os_keychain and not resident_service" -q
    6 failed, 1620 passed, 22 deselected in 110.81s

Four of those six were owner failures and are fixed: the extract payload dropped the new draft fields, and the roundtrip fixture left them at their default. The remaining two are a concurrent lane's uncommitted provenance field and its postal-shape check, both failing on symbols this work does not touch.

The alpha-3 correspondence was mutation-proven specifically, from a plugin outside the repository applied at plugin import so the patch lands before any `from X import name` binding:

    MUTATION=alpha3   the registry correspondence emptied
    11 failed, 33 passed

    MUTATION=alpha2   the already-correct-system pass-through removed
    4 failed, 8 passed

The two mutations red disjoint sets, which is the discrimination that matters: emptying the correspondence reds every Facturae case including the end-to-end territory resolution, while every UBL case stays green legitimately because the alpha-2 leg is untouched, and removing the alpha-2 leg inverts that exactly. Both runs printed the landed-mutation marker, so neither green half is a patch that failed to apply.

## Notes

The dispatch's premise that the read-path country widening had landed was wrong at claim time: it was a concurrent lane's uncommitted working copy, and the visibility assertion named in the brief was green at HEAD while a different assertion, aimed at the parser's own fields, existed only in that lane's working tree. Both were replaced.

No test fixture was edited and no provenance sidecar was restamped. The Facturae specimen already states the country element, and the UBL specimens carry no address block at all, so the sibling suite's established technique was followed instead: inject the element into a copy under the test's temporary directory and never write the corpus tree.

The bulk of this work reached the repository inside another lane's whole-index sweep commit rather than through a commit authored here, and the plan row was closed by a third party before any execution record existed. The row was therefore already checked with nothing recording what was delivered, which is what this record now supplies.
