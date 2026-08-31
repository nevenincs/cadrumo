---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:9c42fd838b9cd98b18dc19063391ef8e7033bf9edb2b56d210a46746a4c53b9f'
step_id: 'S145'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Align the ledger export payload with the row it claims to mirror on all thirty-one fields, and repoint the currency case that my own earlier consolidation had turned into a non-wall

## Scope

- `src/cadrumo/entrypoints/cli/_ledger_payloads.py`
- `src/cadrumo/application/ledger/models.py`
- `src/cadrumo/entrypoints/cli/tests/test_ledger_interface_contract_payloads.py`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_ledger_payloads.py`
- `M` `src/cadrumo/application/ledger/models.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_ledger_interface_contract_payloads.py`
- `verify:` field-by-field metadata comparison -> no field differs between payload and row
- `verify:` probed both on eur / " EUR " / EURO / 12A / X / empty -> identical on every input
- `verify:` `pytest test_ledger_interface_contract_payloads.py + payload gate -n 0 -m ""` -> 26 pass, 1 peer failure

## Notes

The payload docstring says it "mirrors" LedgerExportRow. For four columns it did
not: the canonical row requires content in lifecycle_state, direction,
description and business_classification, and the payload accepted an empty
string in each. A payload LOOSER than the record it projects lets a consumer
validate a row the producer could never emit, so the published schema promised
less than the data actually carries. Both sides now read `NonEmptyStr` -- which
is the alias's own stated purpose, "so a payload cannot quietly disagree with the
model it projects about whether empty is allowed".

### A regression of my own, from an earlier round

One test failure here was mine and older than this step.
`test_export_and_preflight_payloads_use_typed_nested_rows` asserted that a
currency of `"eur"` is REFUSED by the export payload. That was true while the
payload carried a hand-rolled `^[A-Z]{3}$`. An earlier round of this campaign
replaced that with the canonical `IsoCurrencyCode`, which NORMALISES `"eur"` to
`"EUR"` instead of refusing it -- and the narrower test selection run at the time
did not include this module, so it went red and stayed red.

The test's intent survives and is correct: the payload must cross the same wall
as the canonical model. What no longer holds is its example, because after this
step both sides normalise `"eur"` identically. Asserting a refusal there would
now pin the payload as STRICTER than the record it mirrors, which is the exact
divergence the test exists to forbid. The case is repointed at `"EURO"` --
currency-as-a-word, a real operator mistake the LLM extraction fixtures carry --
which both sides refuse.

The remaining failure in that module, an `operator_action` field
`LedgerIssuePayload` never declared, is peer-owned: the model carries three
fields and the file is not in this session's diff.
