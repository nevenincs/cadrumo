---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:232ccdcad71d9f36edc223b6a6534f557b21080180317c1887015098bfab71fc'
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

**The domain's own predicate deliberately cannot serve here**, and that is worth
recording so nobody "fixes" it by calling it. `supply_nature_is_required`
answers from a CATEGORY and returns `True` for `None`, which is correct where it
is used: an operation whose category is open may yet fork. At assembly time no
category exists yet, so consulting it would restore the exact unconditional
demand this Step removes. The branch selector available before a category is the
territorial pair, and that is what the laziness reads.

Where the branch does not fork and no nature was established, a placeholder kind
is supplied. **That is only sound because the branch was checked rather than
assumed:** the domestic rule consults `kind` solely to exclude three
reverse-charge kinds, and neither value this module can produce is among them.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_classification_assembly.py -m unit -n0 -p no:randomly
    16 passed in 3.48s

Sixteen collected, sixteen ran, none deselected. Re-run against **exported HEAD
content alone** — 16 passed — so the claim is about committed code rather than
the shared tree.

Four mutations, all applied at the **demand site** rather than at the domain
resolver, because the placement was the only thing wrong and a gate that
re-proves a predicate this Step did not write proves nothing about this Step:

    demand_unconditionally                  -> 1 failed, 15 passed
    never_demand                            -> 4 failed, 12 passed
    unresolved_scope_stops_asking           -> 2 failed, 14 passed
    indifferent_kind_becomes_a_reverse_charge -> 1 failed, 15 passed

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
