---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:3eefac333082db593deebf3b48a1fbe55e4c24d11d09a726e8785dff347f976a'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-canonical-derivations-adr]]"
  - "[[2026-08-10-casilla-schema-research]]"
---
# `casilla-schema` audit: `S12 four-channel relation consumption`

## Scope

Reviewed W02.P04.S12 against the accepted canonical-derivations decision, campaign plan, research, and repository quality constraints. The scoped production surfaces were `_handoffs.py` and the registry facade; the scoped gates were `test_cross_period_relation_consumption.py` and `test_cross_dependency_contract.py`. The required contract is one facade-exported consumption index covering primary casilla bindings, alternate casilla bindings, formula relation references, and formula binding references, with the old test-private predicates removed and algorithm-only relation references remaining an additive test concern.

## Findings

No actionable findings.

`relation_consumption_index` constructs three immutable sets: all primary and alternate casilla binding declarations, all recursively discovered formula relation references, and all recursively discovered formula binding references. `relation_is_consumed` recognizes either a direct formula relation reference or a target binding present in the union of the casilla and formula binding channels. The implementation delegates expression traversal to the existing production runtime-graph helpers rather than recreating a walker.

Both functions are explicitly exported by `_handoffs.py`, imported by the registry package facade, and listed in the facade's public `__all__`. No compatibility alias, private wrapper, legacy branch, or second production consumption predicate is introduced.

The cross-period consumption tests delete their private recursive walker, private index, and private predicate and consume the public production functions directly. The named M390 regression loads the real bundled 2025 annual snapshot, rebuilds one real `CasillaDefinition` through Pydantic with the relation target moved from primary to alternate, proves no primary casilla binding still names the target, and then proves the canonical predicate consumes it. An exact authoring-tree inspection found no formula occurrence of that relation id or target binding, so the alternate channel is the only remaining consumption route and the test would not pass through a different channel.

The cross-dependency contract deletes its duplicate formula-binding and consumption helpers. Its algorithm-binding relation references remain explicitly additive through `_algorithm_relation_refs(revision) | canonical_consumed_relations`, preserving the distinct algorithm-only channel without folding it into the four-channel registry authority. Other uses of `expression_relation_refs` in that module remain separate formula-attachment assertions, not duplicate consumption logic.

No scoped test uses a fake, stub, mock, patch, monkeypatch, skip, or expected-failure construct. The corpus-wide assertions call production behavior and classify registry relations; they do not mirror the business algorithm.

## Verification

- Both scoped test modules: 18 passed.
- Scoped Ruff: passed.
- Scoped BasedPyright: 0 errors, 0 warnings, 0 notes.
- Scoped `git diff --check`: passed.
- Prohibited test-construct scan: no hits.
- Retired-private-predicate sweep: no `_walk`, `_consumption_index`, `_relation_is_consumed`, `_formula_binding_refs`, or `_formula_relation_refs` definitions remain in the scoped tests.
- Facade inspection: both public functions have one explicit import and one public `__all__` entry.
- Alternate-channel bite check: the selected real M390 relation target has no formula relation or binding reference in its revision authoring tree.

## Recommendations

No corrective action is required for S12.

Verdict: **PASS.** W02.P04.S12 promotes the complete four-channel relation-consumption contract, repoints the tests to production, and preserves the separate additive algorithm-reference concern without compatibility or duplicate logic.
