---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:d2e7b640aa609c769e6ed2d6fa0efa8f7c88269d47c05799f0f91846677fbe18'
step_id: 'S112'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Make the supply-nature demand lazy so a domestic operation is not asked a question the law does not fork on

## Scope

- `src/cadrumo/application/ledger`

## Description

- Gate the supply-nature demand on whether the territorial scopes put the
  operation on a branch the law forks on.
- Fail toward asking when either scope is unresolved.
- Supply a nature-indifferent kind where the branch does not fork, after
  checking that the branch genuinely ignores it.
- Gate both directions, and gate the placeholder itself.

## Outcome

The demand was unconditional, so **every domestic invoice carried a blocking
gap**. A domestic operation between established parties at a registry rate
resolves identically for goods and services: the operator was being asked a
question with no answer that could change anything, on the common path.

The territorial scopes were already resolved ten lines above the demand and
simply unused. The laziness now reads them, and **fails toward asking** — an
unresolved scope forks, because an operation not yet placed may still land on a
branch that needs the answer.

**The first fix was a second copy of the laziness rule, and it was corrected.**
It branched on the territorial scopes at the demand site — which is precisely
what `supply_nature_is_required`'s own docstring forbids: *"the laziness rule,
in one place so it cannot be answered differently at two call sites."* It would
have worked, and it would have drifted the moment a category moved between the
nature-indifferent set and the forking one, with nothing to catch it.

**That function still cannot be called here**, and the reason is structural
rather than an oversight: it keys on an established `IvaCategory` and returns
`True` for `None`, while this assembly is what builds the criteria the category
comes FROM. Consulting it at the demand site restores the unconditional demand
it exists to prevent.

**So the answer comes from the one authority that can be consulted before a
category exists: the table itself.** Classify the same operation under each kind
a printed nature can produce and compare the verdicts. Identical verdicts mean
the answer could not have mattered. Measured:

    domestic pair    -> domestic_general, domestic_general        (agree)
    ES to EU pair    -> intra_community_supply, domestic_not_subject  (differ)

No hand-listed scopes, no provisional category standing in for the classifier's
output, and no second key. **And the probe agrees with the domain authority on
every category it reaches** — a gate asserts that agreement, so the two cannot
fork silently.

Where the branch does not fork and no nature was established, a placeholder kind
is supplied. That is sound because the probe proved the indifference for that
specific operation rather than assuming it from a category list.

The probe needs otherwise-complete criteria, so an operation missing a scope or
a date cannot be probed. The nature gap is still **reported** there: failing
toward asking is the rule, and dropping it would cost the accumulate-at-once
property — an operator resolving four gaps would re-run only to meet a fifth.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_classification_assembly.py -m unit -n0 -p no:randomly
    17 passed in 4.26s

Seventeen collected, seventeen ran, none deselected. Re-run against **exported
HEAD content alone** — so the claim is about committed code rather than
the shared tree.

Four mutations, all applied at the **demand site** rather than at the domain
resolver, because the placement was the only thing wrong and a gate that
re-proves a predicate this Step did not write proves nothing about this Step:

    demand_unconditionally                    -> 1 failed, 16 passed
    never_demand                              -> 2 failed, 15 passed
    indifferent_kind_becomes_a_reverse_charge -> 1 failed, 16 passed
    probe_only_one_kind                       -> 2 failed, 15 passed

The second is the load-bearing one. **"No longer demands it" is satisfiable by
never demanding it at all**, which would silently delete a real refusal from the
population that needs one — so the cross-border direction is gated as hard as
the domestic direction.

### The gate was wrong on the first pass and a mutation caught it

`indifferent_kind_becomes_a_reverse_charge` **passed** against the first version
of the suite. The indifference test supplied an explicit nature, so it never
exercised the placeholder at all: pointing the placeholder at a kind the
domestic rule *does* branch on left every test green. The placeholder's
soundness — the entire justification for skipping the demand — was unguarded.

The domestic test now classifies the no-nature path and requires the same
category an explicitly-natured operation yields. The mutation reds.

**That is the second time in two Steps that a mutation found a hole in a suite
that looked complete**, and both times the hole was the same shape: a test
asserting the code *ran* rather than that its *output was right*.

## Notes

The defect was in code this lane wrote two Steps earlier, found by another lane's
RAG sweep for an unrelated Step. Worth stating plainly: the `MissingClassifierInput`
pattern is what made it legible — the spurious row named its own settler, so a
reader could see exactly what was being demanded and ask whether it should be.
A bare boolean gap would have been invisible.

**Discovery caught what the row text did not.** The deliverable-phrased query
returned `supply_nature_is_required` as its first hit, which is the predicate a
reader would reach for and the one that cannot serve. Finding it early is what
turned the design question into "which branch selector exists at this point"
rather than "write a branch table".

No model was loaded, pulled, or contacted. Nothing in `src/cadrumo/llm` was
touched; three files there are held by another lane.
