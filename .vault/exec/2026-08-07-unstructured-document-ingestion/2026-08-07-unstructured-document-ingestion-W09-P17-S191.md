---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:34d64df889fa54455e7da1b9af3885aed9f882849d2588c0459410906efdf997'
step_id: 'S191'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Description

- Add `counterparty_identification_state` to the ledger add command, the patch command, and both CLI payload shapes.
- Declare it as a typed `EUMemberState` Typer option on both `ledger add` and `ledger classify`, so click renders the accepted Member States on a parse failure.
- Carry it through the two field dictionaries the write path builds, the patch resolution, the manual-transaction projection, and the export column set.
- Show it on the single-transaction read surface.
- Add the help and label strings to all four locale catalogues through the `dev.locales` CLI.
- Prove the surface through the real CLI: the fact persists, recording it does not move the establishment axis, withholding it is reported as the missing fact, and an out-of-catalogue value is refused with the accepted set.

## Outcome

The fact Ley 37/1992 art. 25 exempts on can now reach a bank transaction, which
has no document to read a printed VAT prefix from. Before this the field existed
on the model and on no surface an operator could reach, so a row classified as
an intra-community supply refused for something nothing could supply.

The refusal path is unchanged and still fail-closed; what changed is that it is
now resolvable. The readiness report names the identification as the missing
fact, and the option that answers it renders its accepted values rather than a
bare rejection.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_ledger_identification_operator_input.py -m integration -n0 -q
    4 passed in 55.84s

    uv run --no-sync pytest src/cadrumo/application/ledger src/cadrumo/entrypoints/cli -m unit -n0 -q
    1 failed, 2020 passed, 3238 deselected in 262.32s (0:04:22)

The single failure is a CLI module-size budget on `_app_live.py`, a module this
Step does not touch and which was already over budget before it began.

Live surface, confirming the typed option reaches click's accepted-set rendering:

    uv run --no-sync aeat app ledger classify --help
    --counterparty-identification-state <at|be|bg|cy|cz|de|dk|ee|es|fi|fr|gr|hr|hu|ie|it|lt|lu|lv|mt|nl|pl|pt|ro|se|si|sk|xi>

Locale drift gate reports two missing keys, both belonging to a concurrent
counterparty-CLI lane; the four keys added here are absent from its report.

## Notes

The production threading reached HEAD through a sweeper commit rather than one
of mine, as did the earlier part of this work. Only the test file is committed
under its own sha.

A concurrent lane is mid-sweep converting the establishment axis from a stored
field into a value derived from a new counterparty country field, through the
same modules. Its direction agrees with the split this work rests on --
establishment is an address, identification is a registration -- and the two
changes coexisted in the tree without conflict. Two consequences worth carrying:

Its intermediate state broke every ledger read for a period, because the derived
accessor referenced a field not yet added. A property raising `AttributeError`
internally is re-reported by Python under the OUTER attribute name, so the error
read as "no attribute counterparty_eu_member_state" when the missing name was
the country beneath it. That masking cost a diagnosis pass.

Its CLI flag rename landed in the working tree while these tests were being
written, which broke two of them. They were rewritten to read the establishment
axis off the record instead of setting it through a flag whose name is in
motion. The proof that the two axes may legitimately DIVERGE therefore lives
against the aggregation gate rather than here, which is the better home for it:
that is where the money moves.
