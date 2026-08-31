---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:2d678fcd8e8b4ee3b5da6a35dc771381e00cb428bed2c341831940953d2ae348'
step_id: 'S151'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Close the three currency sites the collision had been hiding, including a patch command that accepted a currency its own create command refuses

## Scope

- `src/cadrumo/application/ledger/models.py`
- `src/cadrumo/entrypoints/cli/_ledger_payloads.py`

## Changes

- `M` `src/cadrumo/application/ledger/models.py`
- `M` `src/cadrumo/entrypoints/cli/_ledger_payloads.py`
- `M` `src/cadrumo/core/tests/test_currency_fields_use_one_annotation.py`
- `verify:` `pytest application/ledger/tests -k "patch or manual" -n 0 -m ""` -> pass (96)
- `verify:` `pytest both class gates -n 0 -m ""` -> pass (10)

## Notes

With the key collision fixed, the currency gate immediately reported three sites
it had been hiding. One is a defect worth naming.

`ManualLedgerTransactionCommand.currency` is the canonical annotation.
`ManualLedgerTransactionPatch.currency` -- the same operator, the same field, on
the update path rather than the create path -- was `str | None`. So an operator
could not CREATE a ledger row with a malformed currency but could EDIT one into
having it. The create/patch pair is exactly where this hides, because the two
models sit a hundred lines apart in one file and the patch legitimately differs
by making every field optional; the annotation change rides along unnoticed
inside that legitimate difference.

`LedgerListRowPayload.currency` was a bare string on the row that renders stored
transactions, adopted.

The third is declared rather than adopted: `EvidenceExtractResult.currency` sits
beside `taxable_base` and `iva_rate`, also strings, for the reason that payload
exists -- it shows the operator what the extractor READ from a document,
including when what it read is wrong. Refusing it at the model boundary would
discard the evidence the operator is being asked to review.
