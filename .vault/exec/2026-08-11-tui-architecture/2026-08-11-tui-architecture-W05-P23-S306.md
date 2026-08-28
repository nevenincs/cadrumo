---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:bb16fa0027d9e6fb58f782a95ca2ebd1996ab8260c4d4178c24a8bec4f9750b0'
step_id: 'S306'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Build the typed Modelo Workspace refresh target and the per-operation resolver mechanism that produces it, which no operation has despite one Step already claiming to have delivered it: the type exists nowhere in the tree, OperationDefinition carries no resolver field or hook, and the rename enrolment that names the refresh target in its own title contains no reference to one, so every later enrolment inherits the same silent omission; define the typed target, add the registration point an operation definition uses to resolve into it, and prove a real enrolled operation resolves a genuine target rather than the generic operations-layer request envelope that exists today

## Scope

- `the operations registry OperationDefinition schema`
- `the modelo operation definitions module`
- `the typed refresh target`
- `and a real per-operation resolution test`

## Changes

- `M` `src/cadrumo/application/modelo/workspace_models.py`
- `M` `src/cadrumo/application/modelo/operation_definitions.py`
- `A` `src/cadrumo/application/modelo/tests/test_workspace_refresh_target_resolution.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace_refresh_target_resolution.py -m unit -n0` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tests/test_operation_composition.py src/cadrumo/entrypoints/tests/test_no_dormant_operation_definitions.py -m integration -n0` -> `pass`
- `verify:` `build_production_operation_registry()` constructs 20 definitions -> `pass`

## Notes

The originating row's premise was false and the scope was narrowed on that
basis. The row states the type exists nowhere, that `OperationDefinition`
carries no resolver field or hook, and that no enrolment references one. The
hook was already shipped: `workspace_refresh_adapter` on the public
registration, arity-validated, with a paired-declaration invariant and a
working consumer in `OperationWorkspaceRefreshTargetService`. What was true
is that no production definition registered one, so resolution returned
`REFRESH_ADAPTER_UNAVAILABLE` for all eleven. Only the typed Modelo target,
its registration and its proof were built. A later reader should not hunt for
a mechanism that has been present all along.

Subject validation fails closed rather than asserting an unobservable
contract. The adapter derives the work unit from the settled receipt's
`subject_ref`, but nothing sets that field for Modelo in production yet, so
the convention could not be observed. It is validated through a strict
`WorkUnitId` instead: a malformed subject raises and the resolver returns a
typed refusal, so a different convention reds loudly rather than yielding a
wrong target.

The first registration design was wrong and a shipped gate caught it. One
schema id shared across the seven enrolments left the registry resolving a
binding by first identity match across every registration, so the binding
returned need not belong to the registration being resolved; identical model
types made that harmless only incidentally. The id is now derived per
definition over one shared target model. The gate was not modified and no
exemption was widened.

The enrolment test written for this Step asserted the single shared id and
would therefore have enforced that defect as the contract. It now asserts
per-definition derivation, mutual distinctness and identical schema
fingerprints, so both properties are pinned rather than one traded for the
other.

A mutation proof exposed a weakness in this Step's own fail-closed test. The
first version resolved a foreign subject through the full service and passed
even when the adapter was mutated to trust its subject unvalidated, because
the service revalidates whatever an adapter returns: the test was measuring
someone else's defence while appearing to measure this one. A layered
guarantee that hides which layer is actually holding is how a guard rots
unnoticed. A direct test of the adapter was added, which the mutation reds.

The public-schema registry refused the first target shape, which embedded the
workspace addressing union; one arm of that union is a plain dataclass whose
generated schema carries an open object branch. The model was closed by
spelling the coordinates as typed fields; the closure check was not touched.
The same open dataclass is still embedded in the workspace read contract, so
publishing a workspace request or target through the operations registry will
meet the identical refusal.

A broad commit by another agent captured this Step's files mid-fix and
shipped the superseded shared-id version to the trunk, which is why four
pre-existing production gates were red on the trunk rather than only in a
working tree. The repair landed separately.

Discovery ran on grep and direct file reads rather than the semantic search
service, which was unavailable. The tree's import state broke and recovered
three times during this Step.
