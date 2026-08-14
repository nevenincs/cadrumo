---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:a81874ef29dc51ca622734b54eb86b4d8d1e1df66e0491f7a4b9d28d2fe87a6a'
step_id: 'S26'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# Compute the static import closure from the sanctioned load entry points, diff it against the two traced execution sets, and classify every module reachable but never executed and every one of the 61 non-executing registry modules by owning entry point, marking each live, conditionally reachable with its trigger named, or dead, with dead members deleted and the classification persisted in the census audit

## Scope

- `dev/`
- `src/cadrumo/domain/calculations/registry/`
- `.vault/audit/`

## Description

- Add `dev/registry/load_census.py`: the static load closure over the two sanctioned
  entry points, the symbol-level facade reference map, resolved dynamic-import edge
  harvesting, subprocess load traces for three entry points, and the derived census
  universe with an unclassified residue.
- Add `dev/registry/load_census_classification.py`: the reviewed classification of
  every universe member as live, conditionally reachable with a named trigger, or
  dead, resolved by exact member then longest prefix.
- Add the completeness gate under the registry test package: every universe member
  carries exactly one classification, no rule is stale, every dead candidate is
  adjudicated, the closure is confirmed against `sys.modules` after a real load, and
  a planted module is refused.
- Persist the census as a vault audit with ten findings, each dispositioned.

## Outcome

The static closure holds 509 modules, 148 of them in the registry package, confirmed
against `sys.modules` after a real load. Traced execution reproduces the campaign's
prior figures exactly: warm 22 registry modules and 3 of 42 validators, cold 93 and
36, warm a strict subset of cold, 61 registry modules executing in neither regime. A
third entry point was added because the load alone attributes too little -- inspection
snapshot construction across all 73 bundled modelos executes 61 registry modules and
27 validators.

The census universe is 523 modules: the closure, the eight modules it reaches only
through a dynamic import the static graph cannot represent, and every production
module file in the registry package. All 523 carry exactly one classification -- 187
live, 336 conditionally reachable, 0 dead -- and the gate refuses the tree if any
member does not. Inside the registry package the split is 94 live and 60 conditionally
reachable across 19 named triggers.

Nothing was deleted. The step's deletion clause has no members, and the empty set is a
measured result: two modules read as dead on the module-level import graph and both
turned out to be consumed by registry gates importing them through the package facade,
which is why the reference map is symbol-level.

The census corrects one premise the plan carries. None of the six validators recorded
as executing in neither load regime is unable to execute: four run under inspection
snapshot construction, one publishes the caches the validator binds at import and
defines no callable of its own, and one is reached from a cold-load validator and
fires only on a corpus divergence the bundled corpus does not present. That belongs to
the validator-classification row, not to this one, and is relayed rather than acted on.

Deletion-inventory entries consumed: none. The inventory assigns the six validators to
the validator row and protects the non-executing modules belonging to post-load
surfaces; this step classified both populations and deleted from neither.

Gate bite proof: an empty module dropped into the registry package produced one
unclassified member and exit code 1; removing it restored exit code 0. Nothing under
`src` was modified for the proof, and the tree was left clean.

## Notes

Peers were writing `_schema.py`, `_loader.py`, `_loader_cache.py`,
`_loader_fingerprints.py` and `_schema_base.py` throughout. One census run observed a
transient 155-module package where 154 is stable; the figures above were taken from a
settled run and re-derive on demand.

The warm regime turned out to be a caching state rather than a population. Three
consecutive warm traces taken immediately after peer edits landed produced 44, then
22, then 22 executing registry modules: the first load re-certified the moved tree
fingerprint and was partially cold. Every warm-regime bite proof the plan requires
should load once to settle before measuring.

Two tree-wide gates are red at this revision and neither names anything this step
added: the import-linter `Core must not import outer layers` contract, broken by a
test-module chain reaching `application.aggregation`, and seven cases in the import
hygiene gate whose named violations are in the adapters, application and entrypoint
layers. Both are reported to the campaign rather than absorbed here.

Five production dynamic-import sites remain unresolved and are reported unclassified.
There is no sanctioned inventory of first-party function-local import edges in this
repository, so they are reported on the graph difference alone; nothing in this step
should be read as an allowlist having cleared them.
