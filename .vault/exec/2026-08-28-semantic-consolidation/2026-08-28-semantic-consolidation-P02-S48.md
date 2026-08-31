---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:5eb4f4cd0b59e98aa90d648eff7d205b474ef7643c382b4e17fae10cd0df5fd9'
step_id: 'S48'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Migrate the export-row date and non-negative-amount checks the CLI enforces onto the canonical export row, which declares no validators at all

## Scope

- `src/cadrumo/application/ledger/models.py`

## Changes

- `M` `src/cadrumo/application/ledger/models.py`
- `M` `src/cadrumo/entrypoints/cli/_ledger_payloads.py`
- `verify:` canonical row probed -- refuses a non-date, a negative amount and NaN; accepts the empty absent-column spelling
- `verify:` `pytest application/ledger/tests -k "export or model" -n 0 -m ""` -> 109 pass, 1 unrelated
- `verify:` `pytest cli test_ledger_interface_contract_payloads.py -n 0 -m ""` -> 19 pass, 1 peer failure

## Notes

The canonical export row declared no validators at all while the CLI projection
of it carried three: two date checks and the non-negative amount rule. The rules
now live on the row.

That siting is the whole point rather than a tidiness preference. `LedgerExportRow`
is what the export writes, and a rule enforced only on the way out through JSON
left the CSV and the persisted snapshot ungoverned -- the JSON envelope is one
of several things built from this row, not the gate in front of them.

The projection KEEPS its copy, and that is a decision worth stating because it
looks like the duplication this campaign removes. It is not: an output payload
that promises less than the record it mirrors is the divergence this same module
has been corrected for twice already, once on four string bounds and once on a
currency. What matters is that both sides now ask the SAME two predicates,
`parse_iso8601_date` and `is_non_negative_canonical_decimal`, so the rule is
stated once and checked twice rather than written twice.

Probed rather than assumed on the one case that could have broken real data: the
serializer spells an absent optional column as `""`, and both the empty
`value_date` and an empty `taxable_base` are still accepted.
