---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:094019c7c3343a04a7d5f13b57f7ef06be85a2325213de8c6c13033611592908'
step_id: 'S31'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---
# add a fixture-anchor assertion beside every test that intersects a candidate set against UNMODELED_OBLIGATIONS, which is currently EMPTY so any such intersection assertion passes vacuously and keeps passing if the filter it guards is deleted, gating instead on the PROPERTY the filter guarantees so the test stays meaningful whether the collection is empty today or populated tomorrow, verified by the anchor failing when the constant is empty and by the property assertion failing when the filter is removed

## Scope

- `src/cadrumo/core/tests`
- `src/cadrumo/application/live/tests`

## Description

- Swept every Python site intersecting a candidate set against the recognized-unmodeled obligation declaration: six assertion sites across five modules, one of which the live-history discovery module had already converted to a containment property in an earlier commit.
- Replaced the overview coverage module's vacuous equality with a property exercise of the registry-unmodeled disposition over a non-empty declaration naming a genuinely registry-less obligation, guarded by a baseline half that proves the substitution reached the live holder.
- Parameterised the coverage test module's universe and partition helpers on the declaration the builder was actually given, so the totality invariant can be checked against a non-empty declaration.
- Added a core-level consistency gate for the declaration itself: blank description, an entry also declared out of scope, and an entry absent from the non-registry set are each named by a pure checker, with a second test proving the checker names every offending shape while the real declaration is still empty.
- Removed the vacuous non-membership assertion from the four registry batch modules and narrowed their test names to the registry-backed property they actually prove; the declaration-side guarantee now lives once in the core gate rather than repeated six times over an empty mapping.

## Outcome

The disposition the declaration exists to trigger is exercised. Before this change the branch classifying a recognized obligation the registry cannot model was unreachable through the real declaration, and the test claiming to cover it compared two empty sets; both the assertion and the branch could be deleted independently with the suite staying green.

The property now gated is not the emptiness of the declaration and not a count. It is that a universe member outside the registry directory reaches exactly one disposition, carrying the registry-unmodeled reason, and that the declaration cannot contradict its own contract in the three ways that would make a declared obligation invisible to an operator. Both hold whether the declaration is empty today or populated tomorrow.

One thing the standing goal asks that this does not deliver: the disposition is reached through the declaration the builder reads rather than through a populated production declaration, because none exists. Substituting the declaration exercises the real registry load, the real universe union and the real disposition walk, but it does not prove any actually-declared obligation is correct, since there are none to be correct about. The first real entry inherits a gate that already bites.

## Verification

    uv run --no-sync pytest -n0 -q src/cadrumo/core/tests/test_unmodeled_obligation_declaration.py src/cadrumo/application/overview/tests/ src/cadrumo/core/tests/test_modelo.py
    242 passed in 32.43s

    uv run --no-sync pytest -n0 -q <the four registry batch modules>
    33 passed in 21.07s

Mutation proof one, the disposition filter. The branch classifying a non-registry universe member was removed from the coverage module in a narrow window; the replacement asserted its single occurrence was found before writing, printing "MUTATION APPLIED, holder found, 1 occurrence removed", so the run cannot have been a no-op.

    uv run --no-sync pytest -n0 -q src/cadrumo/application/overview/tests/test_obligation_coverage.py
    1 failed, 10 passed in 21.23s
    FAILED ...::test_a_recognized_unmodeled_obligation_is_advised_not_invisible
    assert <CoverageAdviceReason.APPLICABILITY_UNDETERMINED> is <CoverageAdviceReason.REGISTRY_UNMODELED>

The same run is the evidence that the replaced assertion was vacuous: with the filter deleted, the retained declaration-equality test stayed green. The module was restored from bytes captured with git show before the window opened, and is byte-identical to the committed version.

Mutation proof two, the declaration checker. One of its three clauses was removed, again with a found-the-holder assertion before the write.

    uv run --no-sync pytest -n0 -q src/cadrumo/core/tests/test_unmodeled_obligation_declaration.py
    1 failed, 1 passed in 2.28s
    AssertionError: assert '510: declared unmodeled AND out of scope' in ['037: no recorded description', '038: declared unmodeled but absent from NON_REGISTRY_MODELOS']

Restored, then 2 passed in 1.20s.

Type and lint gates on the touched modules: ty check reported "All checks passed!", ruff format reported both files already formatted, ruff check clean.

## Notes

The tree-wide import-hygiene gate is red on three test-debt assertions, all naming a peer's in-flight ledger filer-identity seam module. Neither the new core module nor the edited coverage module appears in that output; the coverage module's reach into its own package's private module is intra-package and outside the gate's scope.

The declaration substitution is a monkeypatch of a module-level data constant, not a behavioural test double. It is the only way to populate a declaration that is empty in the tree, and the alternative considered and rejected was a production parameter existing solely for tests. The baseline half of the test is what keeps the substitution honest: it asserts the module attribute is still the same object the core package exports, so a refactor moving the read elsewhere fails loudly rather than leaving the substitution inert.
