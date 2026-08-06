---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:201f5e6e676b2fe0e5f00112da02d7312cc6a5dfe785c4df570bfcdb24f09ae2'
step_id: 'S28'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Drive a received invoice through to the committed Modelo 111 binding values, asserting the filed casillas against the invoice figures rather than stopping at the aggregation totals

## Scope

- `src/cadrumo/application/aggregation/tests/test_invoice_retencion_routing.py`

## Description

- Carry the received-invoice retención assertion past the aggregation totals to the committed Modelo 111 binding values.
- Assert the filed casillas against the invoice's own figures rather than against the aggregate the projection returns.

## Outcome

Landed as commit `32ef16114d`, "test(aggregation): carry the received side to its filed casillas, not just its totals".

RECONSTRUCTED RECORD. Written on 2026-08-06 from the commit and its diff, not from a contemporaneous account. The Step was checked without a record and is being reconciled under the plan-closure rule; what follows is what the commit demonstrably does, with no verification claimed that cannot be re-run today.

The distinction the Step turns on is real and worth restating: an assertion that stops at the aggregation total proves the projection sums correctly, and proves nothing about whether the figure reaches a filed casilla. Only the binding-value assertion crosses that boundary.

## Verification

Verification is re-runnable rather than quoted from the original session:

```
uv run --no-sync pytest src/cadrumo/application/aggregation/tests/test_invoice_retencion_routing.py -n 0 -q
```

A LATER FINDING BEARS DIRECTLY ON THIS STEP AND MUST TRAVEL WITH IT. The routing primitive this module tests -- `route_invoice_retenciones` -- has ZERO production callers, verified 2026-08-06. The test proves the projection is correct; nothing in production invokes it, so a received invoice's retención does not reach Modelo 111 in practice. This Step's assertion is sound and its subject is unreachable. That is precisely how the gap survived: a correct test over dead capacity. Tracked as the P06.S47 wiring work.

## Notes

Reconstructed under the plan-closure rule after `vault plan status` reported this Step checked with no execution record. The commit was located by SCOPE FILE, never by step id: a bare `git log --grep=S##` returns commits from other campaigns, because step ids are per-plan and collide across plans. That search returned confident, plausible, entirely wrong matches for every one of the nine unrecorded steps before the namespace error was caught.
