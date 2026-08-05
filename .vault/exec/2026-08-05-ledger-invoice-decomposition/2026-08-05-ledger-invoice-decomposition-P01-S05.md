---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:e213f26413e8dc605553ca5cc67252eb5c13665d285488a1c3cc8bf7d12e660c'
step_id: 'S05'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Surface the missing-substrate advisory on both the preflight and calculate paths through the typed notice channel

## Scope

- `src/cadrumo/application/modelo/_calculation_actions.py`

## Description

- Add an ungrounded-income-substrate reason to the calculation source diagnostic vocabulary.
- Emit one diagnostic per aggregation from the renta income source resolver, carrying the exact contributor count, the summed cash, a bounded sample of transaction ids with the remainder stated, and the remediation verb.
- Describe the consequence per declared fact, since the two base-reading facts fail in opposite directions.

## Outcome

Landed in commit `bdafb805b3`.

The advisory rides the existing typed notice channel: a calculation source diagnostic is already projected into a warning-severity notice with its structured provenance on the notice context, so no bespoke field was added to any output schema and the no-bespoke-notice-field conformance gate stays green (162 passed, integration lane).

Fired once per aggregation rather than once per row, per the crying-wolf constraint the governing decision names - the actionable unit is how much of the declared income has no invoice behind it, not each row. The count and summed cash are exact; the id list is capped with the remainder stated, so the truncation is visible rather than a silent cap.

Test evidence: JSON schema conformance 162 passed (integration lane); aggregation and ledger suites 1086 passed.

## Notes

TWO DIVERGENCES, both reported rather than papered over.

First, the Step scopes the work to the modelo calculation-actions module. No edit was needed there: that module already projects every source diagnostic generically, and the CLI already turns each into a notice. The change belongs in the resolver that BUILDS the diagnostic, which is the aggregation modelo-bindings module - where the sibling unrouted-observation screen already lives. Editing calculation-actions would have added a second, parallel projection path.

Second, the Step asks for the advisory on BOTH the preflight and calculate paths. The preflight half was ALREADY COVERED before this campaign and no work was manufactured to fit the Step. The IVA missing-fact predicate flags any classified non-trabajo row lacking a taxable base, and the preflight catalogue maps it to its own missing-taxable-base reason - an incoming actividad row with no base surfaces there today. Adding a second income-specific preflight issue for the same transaction would double-report it, which is the crying-wolf failure the decision names. The genuine gap was the calculate path, and that is what this Step closed.

Worth a follow-up decision, not actioned here: the preflight detail text reads "transaction has no taxable_base fact", which is IVA-framed and does not name the income consequence. Sharpening it would touch the shared IVA detail map, so it needs its own scope.

A prior semantic sweep confirmed the canonical mechanism: the settlement-grade advisory module surfaces a structural under-declaration gap through the same non-blocking diagnostic. This advisory follows that pattern rather than inventing one.
