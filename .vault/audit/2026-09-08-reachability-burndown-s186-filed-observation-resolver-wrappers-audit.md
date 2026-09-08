---
tags:
  - '#audit'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:a3b31892dc7dde43d477f5a3369c057f0201b575ff9908b724cb1b779b8d7723'
related: []
---

# `reachability-burndown` audit: `s186 filed observation resolver wrappers`

## Scope

Independent closure review of Step S186 against the reachability plan, filed-observation identity grounding, and accepted calculation aggregation taxonomy. The review covered the complete observation conversion facade, migrated binding and relation tests and support, and the live `verify_filed_state` application owner. It checked reachability evidence, semantic parity, layering, exports, imports, and focused verification without modifying production or test code.

## Findings

No findings.

The baseline call graph contains `resolve_previous_filing_bindings_from_filed_declarations` and `resolve_relation_values_from_filed_declarations` only at their definitions, facade exports, documentation, and their dedicated tests. The worktree contains neither name. Both deleted implementations only mapped `registry_observation_from_filed_declaration` across observations, translated `Period` to `period.registry_token`, and invoked the canonical domain resolver.

The migrated test support performs the same conversion and argument translation before calling `resolve_previous_filing_binding_values` or `resolve_relation_values_from_observations`. Binding and relation assertions, missing and duplicate source refusals, incomplete-coverage refusal, encrypted-store round trip, filing year, and period semantics remain intact. Adding `registry_snapshot_ref` to fixture observations satisfies the current observation contract and creates no production facade or duplicate owner.

The live `verify_filed_state` path already loads filed observations, converts them with `registry_observation_from_filed_declaration`, and calls both canonical domain resolvers before calculation. It remains the application owner, consistent with the aggregation taxonomy: previous-filing values enter `binding_values`, while cross-model relation values enter `relation_values`. No live behavior depended on either removed adapter wrapper.

Wrapper-only resolver and identifier imports and exports were removed from `declarations_observations`; exact search finds no stale wrapper reference outside historical vault records. Ruff passes across the four S186 facade and test paths. The migrated binding and relation classes pass 17 tests, and the executor records 19 focused passes. The peer-owned fixed-width/export-policy failure occurs during submitted-file parsing before either migrated resolver is invoked and is unrelated to this step.

The live measurement is 345 exact unused symbols and 18 orphaned tests, with both targeted findings absent.

## Recommendations

Close S186. No follow-up is required for this step; keep the peer fixed-width/export-policy failure with its owning work.
