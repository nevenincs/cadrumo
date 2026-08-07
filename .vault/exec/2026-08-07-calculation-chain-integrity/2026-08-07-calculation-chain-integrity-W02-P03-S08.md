---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:4d61ee17296ad808e584628239231ed55d048c916f0cfb0c93cdaca5e44ad14c'
step_id: 'S08'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W02.P03.S08

## Outcome

Mutation-proved the gate, and stated in code what it cannot catch — including the part that is uncomfortable to state.

## The mutation proof

`test_binding_reachability_probe.py` retargets an IVA selector to match nothing by emptying `cash_accounting_treatments`, and asserts the probe raises. Three tests hold it up rather than one:

- **The positive control.** A reachable selector passes. Without it, a probe that refused everything would satisfy the mutation proof while blocking every binding in the registry.
- **The mutation.** The empty-set selector raises `RegistryValidationError`.
- **The premise, proved independently.** The same empty-set selector is driven through the real matcher against every `IvaCashAccountingTreatment` member, asserting none match. Without this the probe could be raising for an unrelated reason and the mutation test would not notice.

The mutation is applied to the **selector**, not to production code, so no tracked file is edited: a peer's sweep cannot commit the mutation and a crashed run leaves no residue.

## What it cannot catch, stated in code

Three limits are named in `_iva_reachability_probe`'s docstring, where a reader meets them:

- It never touches ledger data, so it proves a selector CAN match a shape, never that real data DOES.
- It cannot catch a matcher that accepts the WRONG rows, only one that accepts none.
- It cannot catch a resolver that aggregates correctly-matched rows incorrectly — the residual blind spot the governing ADR already names, and outside what any build-time data-free check can observe.

## The fourth limit, which is the one worth having

The casilla-keyed families' probe is tautological. That is now written in `_renta_gastos_pago_fraccionado_reachability_probe`'s own docstring in those terms — "it also cannot fail as this family is currently matched, and saying so is the point" — rather than left to read as coverage.

It is pinned by `test_a_casilla_keyed_selector_probe_is_structurally_unable_to_fail`, which asserts the matcher accepts a probe built from its own selector for three casilla ids including a nonsense one. If that family's match rule ever tests something the probe does not copy, the assertion reddens and forces the limit paragraph to be rewritten instead of quietly outliving its truth.

Asserting a limit rather than describing it is the difference between a documented weakness and one that silently stops being true.

## Note on the probe kept rather than deleted

The tautological probe costs nothing and becomes live the moment its family's matcher tests a declared set — the shape that makes the IVA sibling bite. The reachability guarantee that family actually has is elsewhere and is real: `target_casilla_id` is validated against `_RENTA_130_GASTO_CASILLAS`, and the revision's casilla set is cross-checked at snapshot build.
