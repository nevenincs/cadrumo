---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:f6458ae0ec78086ba78bb12c0526e8e92a6b38d16c04111519eb1aa4013468bf'
step_id: 'S160'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Adjudicate the gross-amount zero disagreement as deliberate and write its reason at the site, since the reason lived only in a test

## Scope

- `src/cadrumo/domain/renta/_ledger_expenses.py`

## Changes

- `M` `src/cadrumo/domain/renta/_ledger_expenses.py`
- `verify:` `pytest domain/renta -k "ledger_expense or expense" -n 0 -m ""` -> pass (23)

## Notes

Reported as an unexplained disagreement: three income-side `gross_amount` fields
allow zero, the expense-side one forbids it, with no stated reason either way.
Four surfaces, and the trace found three answers:

| surface | a zero amount |
| --- | --- |
| import parse boundary | REFUSED -- "a zero-amount row carries no flow" |
| `RawTransaction.amount` | accepted; only a negative is refused |
| income observation `gross_amount` | accepted |
| expense fact `gross_amount` | REFUSED |

That looked like the campaign's usual shape, and it is not. The income side has a
test that deliberately constructs a zero-value observation and asserts it still
surfaces when unrouted -- an unrouted zero has to reach the operator precisely
because nothing routed it. So `ge=0` there is a modelled case, not an oversight,
and a zero-amount deductible expense is still not an expense.

Adjudicated as DELIBERATE, and the reason written at the field. It had been
carried only by a test, which is the fourth place this campaign has found a
bound's justification living somewhere an annotation cannot show it -- after a
closed set, a codec's declared width, and a shared validator. A reader comparing
the two annotations had no way to reach it.

`RawTransaction` accepting a zero that its own import boundary refuses is left
alone and NOT folded into this: whether a manually entered zero-amount
transaction is legitimate is a separate question from which of two observations
may carry one, and it reaches persisted data.

P08.S29 stays open. Its coefficient third landed in S157 and S159, this is its
gross-amount third, and its taxable-base third is a tax review -- two sites forbid
a zero base and four allow it, proven live in one file, and whether a zero base
imponible is legitimate is the operator's call under the sibling step S39.
