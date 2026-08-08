---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:337d02fce955206857abf269217a2da40789399c54ad2ca950ea0c02b18de266'
step_id: 'S162'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# `unstructured-document-ingestion` exec W09.P17.S162

## Scope

- `src/cadrumo/_data, src/cadrumo/adapters/inbound/einvoice`

## Description

- Search semantically for the CII reader and the country rung before writing anything, then confirm the exact declaration sites with a targeted grep.
- Measure what the CII branch actually exercises today, rather than accepting the row's premise that nothing does.
- Add `_cii_country_code`, reading the party's own `ram:PostalTradeAddress/ram:CountryID`, scoped to the address element so a tax-registration prefix cannot answer a question about place.
- Wire it into the CII parser beside the postal read, and correct the record comment that enumerated only two of the three syntaxes' code systems.
- Add the two CII entries to the structured element-path table, so a CII country cites the element it came from instead of degrading to a sentence naming the shape.
- Author the first standalone Cross Industry Invoice specimen and its provenance sidecar, as the deliberate complement of the UBL code-G fixture beside it.
- Replace the asserted-gap test that pinned this gap with the positive contract it predicted, per that test's own instruction.

## Outcome

The row's premise is wrong in two ways that matter, and both make the delivered work larger rather than smaller. CII is not unexercised: the bundled ZUGFeRD PDF embeds a Cross Industry Invoice, and the parser is already asserted against it field by field, including a two-rate breakdown. And the country data was not absent from the corpus either. That ZUGFeRD document has carried `ram:CountryID` for both parties since the day it was bundled, one element away from the postal code the reader was already taking out of the same address block. The value was present, parsed past, and establishing nothing.

What was genuinely unexercised is narrower and more interesting than "no CII artefact". The shape probe has two routes to the CII shape and only one had ever been travelled: every CII byte in the corpus arrived inside a PDF, so classification happened through the attachment branch, while the standalone branch that carries every UBL and Facturae specimen had no CII document and would have refused one as unrecognised XML with nothing noticing. And the country rung was unlit for CII specifically: helpers existed for Facturae and UBL, and no third one. So CII read each party's postal code and no country at all, which is the worst of the three states, because the postal code is consulted only where country evidence positively names Spain. A syntax this codebase classifies, parses exactly and routes to the exact reader established neither party's territory while carrying every value needed to.

The specimen is authored as the complement of the UBL code-G fixture rather than as another instance of it. That one declares UNTDID 5305 code G and prints no counterparty country, so the category is withheld: a rule table cannot place a party it cannot locate. This one declares the same code and supplies the evidence the other lacks. The pair discriminates "the code was honoured" from "the code was honoured because nothing checked where the party is", which neither document can do alone. Its two parties are in different countries on purpose, because every existing case in the country suite asserts the same code on both sides and would accept a reader that resolved one party's element twice.

## Verification

A mutation plugin resident outside the repository, patching the production reader and the element-path table. No tracked file was mutated. Five modes; the baseline is asserted before each, and the observable read-back is taken through the production entry point rather than from the patch reporting success.

    CIIMUT_MODE=blind    -- the pre-change state, reader returns None
    [ciimut] RUNG 3: production entry point now reports (None, None)
    7 failed, 42 passed

    CIIMUT_MODE=seller   -- both parties resolve through the seller's block
    [ciimut] RUNG 3: production entry point now reports ('ES', 'ES')
    5 failed, 44 passed

    CIIMUT_MODE=nopath   -- the CII element paths are dropped
    [ciimut] RUNG 3: element path degraded to "the xml_cii record's supplier_country_code"
    1 failed, 48 passed

    CIIMUT_MODE=prefix   -- the country is read off the VAT registration
    1 failed, 23 passed

    CIIMUT_MODE=blind, against the replaced gap test
    1 failed, 40 passed

A fifth mode found a real hole rather than confirming the work. A subtree-walk defect produced NO observable change on the specimen: realistic data has a party's VAT prefix agreeing with its country, so `CHE116281277` and `CH` cannot be told apart, and the claim that the read is scoped to the address block was asserted in a docstring and tested by nothing. The rung-three assertion refused to proceed rather than reporting a green. The fix is a case that constructs the divergence a realistic fixture cannot contain: the same Swiss-established buyer carrying a German VAT registration, which is an ordinary arrangement and the one shape that separates the two readers. A prefix reader answers DE and settles an EU member; the address reader answers CH and settles a third country. Under `prefix` that case reds alone while the corpus specimen still reports ES and CH, which is the finding stated as a passing gate.

The asserted-gap test that pinned this gap went red as designed. Its docstring and its `test_asserted_gap_` prefix both instruct that a red means the gap CLOSED and the test must be replaced rather than relaxed; it was replaced with the positive contract, on the same document byte for byte, pairing the recovered country with the Canarias scope its postal code resolves to.

    uv run --no-sync pytest <ladder, country-codes, corpus-parsing, einvoice adapters> -n0 -q
    120 passed in 15.13s

    uv run --no-sync pytest src/cadrumo/application/ledger/tests src/cadrumo/adapters/inbound -n0 -q
    1986 tests ran; 89 deselected by -m 'unit and not external_tool and not os_keychain'
    6 failed, 1980 passed, 89 deselected in 307.15s

    uv run --no-sync ty check <changed modules>   All checks passed!

## Notes

Of the six failures in the wide run, one was the asserted-gap test and is closed above. Three are the draft-to-payload parity gate, failing on `supplier_stated_country_code`, `customer_stated_country_code` and `refused_anchor` -- none of which this Step touched. Measured at HEAD: the draft carries fourteen occurrences of the stated-country field and the CLI payload model carries zero, so the gate is red at HEAD independently of this work, and the payload module is currently being edited by another lane. That is the seventh-amendment country-vocabulary campaign mid-flight. The remaining two are M390 declaracion parser cases, a different surface entirely. None absorbed, because absorbing would mean editing files belonging to active peer campaigns.

Two lint errors under `ruff check` on the ledger package are duplicate dictionary keys in the package facade. Both are present at HEAD and the file is peer-dirty; not this Step's.

Readings are HEAD. A concurrent sweeper committed most of this Step's working copy mid-flight in a bare commit, so the parser change, the element-path entries, the specimen, its sidecar and both extended test modules landed inside a peer's commit; only the gap-test replacement was committed under this Step's own explicit pathspec. Both were verified present at HEAD before this record was written, and the peer WIP that shares one of the touched files was deliberately left uncommitted rather than swept in by a pathspec commit.

The row scopes this Step to `src/cadrumo/_data` and the einvoice adapter package. The specimen went to the evidence corpus beside the UBL and Facturae specimens it complements, which is under the ledger test tree rather than `_data`; `_data` holds AEAT record schemas, not invoice specimens. The scope is recorded above as the row wrote it.

The unit lane only. The integration lane was not run.
