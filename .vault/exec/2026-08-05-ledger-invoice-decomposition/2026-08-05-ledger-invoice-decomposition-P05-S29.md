---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:7eb5bc6e26dbc1d766d5730b30a92ad813477f163ec2f03ca55b1f78e6e01640'
step_id: 'S29'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---
# Drive the same invoice through to the committed Modelo 303 repercutido bindings so the IVA leg reaches a filed casilla like the income and retenciones legs already do

## Scope

- `src/cadrumo/application/aggregation/tests/test_cross_domain_invoice_scenario.py`

## Description

- Extend the cross-domain scenario, which already drove the income and retenciones legs through the committed Modelo 130 bindings, to drive the IVA leg through the committed Modelo 303 repercutido bindings.
- Resolve the Modelo 303 revision through the production registry authority rather than a test-side snapshot builder, so the bindings asserted are the ones a real calculate loads.
- Assert Modelo 130 casilla 01 and the Modelo 303 repercutido base each against the invoice figures directly, never against each other, so two registries agreeing on a shared wrong number still fails.

## Outcome

Landed as commit `3c751c4153`, "test(aggregation): carry the IVA leg to its filed casillas, not just its observation".

RECONSTRUCTED RECORD. Written on 2026-08-06 from the commit and its diff, not from a contemporaneous account. The Step was checked without a record and is being reconciled under the plan-closure rule; what follows is what the commit demonstrably does, with no verification claimed that cannot be re-run today.

The commit's stated rationale matches the Step exactly: before this landed, only two of the three domains reached a filed casilla for the shared invoice -- income and retenciones were driven to Modelo 130 bindings, the IVA leg stopped at the observation and never crossed the modelo boundary (the cuota is filed under Modelo 303, a different modelo, revision, and resolver). Mutation-proved per the commit message: asserting the repercutido base against the credited cash instead of the declared base reddens the module.

## Verification

Verification is re-runnable rather than quoted from the original session:

```
uv run --no-sync pytest src/cadrumo/application/aggregation/tests/test_cross_domain_invoice_scenario.py -n 0 -q
```

## Notes

Reconstructed under the plan-closure rule after `vault plan status` reported this Step checked with no execution record. The commit was located by SCOPE FILE, never by step id: a bare `git log --grep=S##` returns commits from other campaigns, because step ids are per-plan and collide across plans. That search returned confident, plausible, entirely wrong matches before the namespace error was caught.
