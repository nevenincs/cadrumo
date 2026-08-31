---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:e5dccdcd7e6835bd3407dc7fded9dd2e19e314fa24c550f6c194c9b249feede1'
step_id: 'S147'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Type the constraint comparison so it stops reporting stringified decimals as disagreements, then consolidate the currency policies it exposes and gate the field class so the fifth one cannot land

## Scope

- `src/cadrumo/domain/invoices/models.py`
- `src/cadrumo/domain/modelos/ledger_filing_snapshot.py`
- `src/cadrumo/application/`
- `src/cadrumo/core/tests/test_currency_fields_use_one_annotation.py`

## Changes

- `A` `src/cadrumo/core/tests/test_currency_fields_use_one_annotation.py`
- `M` `src/cadrumo/domain/invoices/models.py`
- `M` `src/cadrumo/domain/modelos/ledger_filing_snapshot.py`
- `M` `src/cadrumo/application/invoices/_bulk_import.py`
- `M` `src/cadrumo/application/invoices/_queries.py`
- `M` `src/cadrumo/application/storage/calc_sheets/_records.py`
- `M` `src/cadrumo/application/operations/financial_operand.py`
- `M` `src/cadrumo/entrypoints/cli/_ledger_business_payloads.py`
- `verify:` four policies probed side by side on EUR / eur / " EUR " / E / 12A
- `verify:` `pytest domain/invoices + domain/modelos/tests -n 0 -m ""` -> pass (481)
- `verify:` `pytest the gate + detail-record observations -n 0 -m ""` -> pass (58)
- `verify:` mutation probe, four arms, all RED; tree restored

## Notes

The instrument came first. Comparing constraint metadata between a payload and
the record it projects reported 400 disagreements and the money ones were all
false, because a stringified decimal cannot carry a Decimal bound. Constraints
are now compared only where BOTH sides carry the same underlying type, which
removes that class by construction rather than by filtering.

What the corrected scan surfaced was a fourth currency policy. That is the
number that mattered: I had found and fixed one currency site per round for
four rounds, which meant I was fixing sites and not the class. So the class was
censused -- 48 currency-named fields, 7 canonical -- and probed:

| site | EUR | eur | " EUR " | E | 12A |
| --- | --- | --- | --- | --- | --- |
| invoices.Invoice | EUR | eur | refused | refused | 12A |
| operations.FinancialOperand | EUR | refused | refused | refused | refused |
| modelos.LedgerFilingSnapshot | EUR | eur | " EUR " | E | 12A |
| core.IsoCurrencyCode | EUR | EUR | EUR | refused | refused |

A FILING SNAPSHOT accepted the single character `E`.

Five sites adopted the canonical. Three did not, and the distinction is the
point: `financial_operand` is a registry-AUTHORED declaration where a sloppy code
should fail the author rather than be repaired behind them; `raw_transaction`
already applies the canonical policy through a `mode="before"` validator with its
own error type, and its docstring explains the ordering that makes the padded
` usd ` case work; `_ledger_expenses` is `Literal['EUR']`, which is STRICTER than
the canonical, not looser.

### One adoption was wrong and the tests said so

`detail_record_bindings.Modelo720RowObservation.currency_code` took the canonical
and a test went red: the model already applies a shared `uppercase_alpha_code`
validator to `country_code` and `currency_code` together, which REFUSES a
lowercase code rather than folding it. Adopting a normalising annotation layered
a second policy over the one its sibling field follows. Reverted and declared.

That is the lesson given to the sentinels turned back on my own work: before
adopting a canonical, check what POLICY rides along with it.

### The gate

Structural rather than a list: any field whose name says it carries a currency
code must use the canonical annotation or be declared with a reason. It found
eleven sites the manual census had not ruled on, which is the gate earning its
place on the first run.

Four arms, proved by mutation from outside the repository: a hand-annotated
field, an exception whose reason is a placeholder, the field vocabulary narrowed
to nothing, and an exception naming a field that no longer exists. All four red,
tree restored.

The probe had to run each mutation in a SUBPROCESS. Two arms mutate the gate file
itself, and pytest keeps the already-imported module in `sys.modules`, so an
in-process second run re-uses the cached module and never reads the edit -- it
reported two arms blind that were not. Same failure shape as the xdist one from
the previous round: the mutation never reached, and a probe that changes nothing
reports it in the same words a passing gate uses.
