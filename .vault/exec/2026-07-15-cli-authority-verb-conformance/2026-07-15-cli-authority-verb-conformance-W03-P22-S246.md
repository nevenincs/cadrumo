---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S246'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
  - "[[2026-07-15-cli-authority-verb-conformance-adr]]"
---

# Replace literal-membership namespace checks with a non-vacuous production-root adoption gate that recognizes cadrumo-prefixed declarations, detects local metadata declarations, and proves each storage binding consumes the registered definition

## Scope

- `src/cadrumo/application/tests/test_namespace_registry_adoption.py`

## Description

- Establish that this step duplicates a step already closed under a sibling backlog plan.
- Resolve the file the step cites against the file that actually holds the gate, which are not the same module.
- Test the shipped gate against the step's own requirement of non-vacuity rather than against its docstring.
- Run the gate at the current commit.

## Outcome

Already satisfied. Closed as verified rather than re-implemented.

This step's action text is word-for-word identical to a step in the sibling quality-backlog plan, which is closed. The two steps cite DIFFERENT files, and resolving that is the substance of this record.

This step cites the namespace-registry adoption module. That module is a real gate but a different one: it holds the weaker drift invariant that any namespace literal must equal a value declared in the registry, deliberately not requiring the constant import, because the domain repositories spell the namespace inline to preserve a lazy-import contract that forbids a module-level storage import. It is not the literal-membership allowlist this step targets.

The gate this step actually asks for is the storage namespace adoption module named by the sibling step, and it is present and substantial. Its own docstring states that it replaces the brittle literal-membership check, a hardcoded allowlist of namespace strings, with three production-root scans. Recognition takes the authority set from the registry itself and keys on the cadrumo-family prefix, so a newly registered definition is covered without editing the gate, which is precisely the adoption property the step names. Redeclaration detection walks the package for write sites passing a raw namespace string, sensitivity member, or integer literal instead of a definition-sourced value, and it sees through two evasions: a value reached through a module-level constant is resolved to its bound expression before the raw-literal predicates run, and metadata passed positionally is bound to parameter names before inspection. Consumption proof asserts every bound repository subclass binds its metadata to an attribute of a registered definition.

Non-vacuity is the whole requirement of this step, so it was tested against that rather than against the docstring. The redeclaration scan's expected result is EMPTY on a canonical tree, which is the shape most at risk of passing while measuring nothing. It is guarded correctly. The authority set is asserted non-empty at a floor of forty registered namespaces, and the consumption proof at a floor of fourteen bound classes, so a scan that found nothing to inspect fails rather than passes. Three positive controls assert the detector flags an injected redeclaration, one reached through a module constant, and one passed positionally, and a fourth control asserts a definition-sourced fragment stays clean. That is a known-match set and a known-reject, which is exactly the bar the governing decision record sets.

Run at the current commit as part of a 22-test run covering this gate and the duplication module: all passed. No change was needed or made.

## Notes

Semantic CODE search was degraded and reported itself healthy: 188 indexed sections against roughly 4546 tracked files, with an empty degraded-reasons list. A probe naming the secure-object namespace registry directly returned five hits, all from one unrelated CLI module, and the registry module itself did not appear. That is the truncated-index signature, and it is why the two candidate gate modules were resolved by direct read rather than by search.

The file-citation mismatch between this step and its sibling is the same shape a close review found elsewhere in this campaign, where a step named a module that did not hold its proofs. It is worth treating as a recurring pattern rather than two coincidences: a step's scope citation drifts from the work more easily than the work drifts from the step, and an auditor reading the plan alone cannot see it.
