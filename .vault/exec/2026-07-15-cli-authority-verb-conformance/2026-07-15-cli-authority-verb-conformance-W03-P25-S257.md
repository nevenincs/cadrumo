---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S257'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove scoped and unscoped parity, historical as-of boundaries, invalid-window refusal, shared projection consistency, and the intentional distinction between bindings and casilla detail

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_queries.py`
- `src/cadrumo/application/modelo/tests/`

## Description

- Establish which of the five named obligations the existing suite already proved and which were unproven.
- Derive the parity anchor from registry data rather than from the query service under test.
- Author proofs for scoped and unscoped parity, shared projection consistency, the bindings and casilla-detail distinction, and context immutability.
- Mutation-test the parity assertion to confirm it is load-bearing.

## Outcome

Implemented. Two of the five obligations were already proved; three were not.

The as-of obligations were already covered. One existing test drives four unscoped queries and requires each to refuse, then confirms the same query without the argument still resolves, so the refusal is scoped to the ignored argument and did not break the path. A second resolves a scoped query at a date inside the revision's window and then at a date before every declared window, requiring the second to refuse. That is the historical boundary and the invalid-window refusal, and both are real.

Scoped and unscoped parity, shared projection consistency and the bindings versus casilla-detail distinction were not proved. Four tests were added. The first pins that when both resolution forms land on the same revision every projected describe field agrees while the filing scope stays absent on the unscoped form and present on the scoped one, so sharing a projection did not erase the distinction between the two public forms. The second asserts the casilla, formula and binding row sets are equal across both routes and that the casilla filter still reaches the shared builder and still narrows the result. The third pins the deliberate non-substitutability of the bindings listing and the casilla detail by comparing their field sets in both directions while asserting they agree on the shared scope spine. The fourth pins the context as frozen and extra-forbidding, which is what stops one builder altering what a later builder sees now that several read one instance.

Two anti-tautology precautions were taken. The parity anchor is derived by asking the registry authority which filing years the resolved revision itself declares it covers, so the assertion cannot be satisfied by the query service agreeing with itself. And the parity assertion was mutation-tested: with the binding row builder truncated to three rows, the two routes diverge at 3 against 28 and the assertion would fail, while unmutated they agree. It is load-bearing rather than vacuous.

The suite ran at 25 tests passed, up from 21, with the marker filter overridden. Type checking reports no errors on the changed modules, and the extra-field proof is expressed through validation rather than an unknown keyword argument so it is checked at runtime without a static error.

Committed in `003a2f987d`.

## Notes

Semantic CODE search is degraded and reports itself healthy; the suite and the query module were read directly.

The empirical parity check was run before the assertions were written, so the tests encode observed behaviour. Had the routes disagreed, that would have been a finding rather than something to assert around.

This step has no counterpart in the sibling quality-backlog plan, whose closed as-of step covers only the two obligations that were already proved.
