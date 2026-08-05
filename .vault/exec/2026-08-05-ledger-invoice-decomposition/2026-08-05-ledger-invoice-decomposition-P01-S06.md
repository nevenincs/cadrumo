---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:df9455be6854390b53642b497e1e6b980080f85743eee7faeca62037662febbe'
step_id: 'S06'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Stop taxable_base_sum coercing a missing base to zero, routing base-less rows into the ungrounded class

## Scope

- `src/cadrumo/domain/calculations/registry/_ledger_bindings.py`

## Description

- Replace the taxable-base-sum or-zero coercion with an explicit not-none filter.
- Add the ungrounded income observation screen, covering the base-less rows that a base-reading binding actually consumes, and route them into the ungrounded advisory.
- Prove the ungrounded screen and the existing unrouted screen never double-report the same row.

## Outcome

Landed across two commits: the coercion fix in `73ea70ea41`, the routing in `bdafb805b3`. The Step is closed only by the second - the first was correct but incomplete on its own, and its commit message should not be read as closure.

A base-less row still contributes nothing to the taxable-base-sum fact, and that arithmetic is deliberately unchanged: this fact sums DECLARED bases, and inventing one from cash would fabricate a legal figure the system cannot infer. What changed is that the omission is now visible. The new screen reports the base-less contributors together with which base-reading facts the revision declares, so the advisory states the consequence precisely - taxable-base-sum rows contributed nothing (always under-declaring), ingresos-integros-sum rows substituted bank cash (wrong in a direction that depends on the invoice).

One screen serves both facts because both mis-handle the same missing fact, in opposite directions. Both committed M130 casilla-01 taxable-base-sum bindings are in scope. The M111/M115 bindings that also name the fact route through a different selector class and are untouched.

Test evidence: registry income-binding tests 14 passed, including three new tests - the screen fires on a consumed base-less row and reports both declared facts, stays silent when every row declares its base, and stays silent for a row the unrouted screen already owns.

## Notes

The explicit not-none filter also separates a genuinely-zero declared base from an absent one. Under the or-zero form both took the same branch, since a zero Decimal is falsy - numerically harmless here but a real trap for the next person to touch the line.

The two screens are complementary and were deliberately tested against double-reporting: the unrouted screen catches a row NO binding consumes, this one catches a row a binding DOES consume without the substrate its fact assumes. A row routed to an unbound casilla belongs to the first screen only.

ADVISORY ONLY. No blocking behaviour was implemented; the verify-stage escalation is P04.S14 and is gated on operator ratification.
