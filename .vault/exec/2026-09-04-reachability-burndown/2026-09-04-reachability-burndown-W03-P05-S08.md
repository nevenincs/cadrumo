---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:f185134716aa09ba9c705f9ca5756cb37ac0a9c978f2446c74f194e05be71968'
step_id: 'S08'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Resolve the domain/calculations exact-confidence symbol concentration at its owning boundary

## Scope

- `src/cadrumo/domain/calculations`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/schema.py`
- `M` `src/cadrumo/domain/calculations/registry/schema_scalars.py`
- `M` five registry data-type test modules repointed at the canonical implementation
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/domain/calculations/registry/tests -k "data_type or scalar or schema"` -> `3 pre-existing failures, 364 passed`

## Notes

A two-layer alias chain, and the second layer was only visible after the first was
removed.

`schema_scalars` defined each validator privately, used the private name in its own
`Annotated` type, and bound a PUBLIC alias to it. `schema.py` imported that public alias
under an `_impl` name and bound a second private alias, so tests could import the validator
from `schema`. Neither layer had a production consumer: each `_impl` appeared exactly twice
in `schema.py` -- its import and its alias -- and the public aliases carried a comment
stating they existed to let the schema facade preserve its historical private names.

Removing the outer layer made the count go UP by one rather than down by five, which is
what exposed the inner layer: the public aliases lost their only consumer and became
findings themselves. Both layers are now gone, tests import the private implementation
directly, and `schema_scalars` reports zero exact findings where it previously reported
five. The tree-wide count moved from 1391 to 1387.

One near-miss worth recording. `validate_country_code` appeared to have seven consumers,
which would have blocked its removal. Checking the import SOURCE rather than the name
showed every one of them resolves to `domain.invoices.validators.validate_country_code` --
a different function that happens to share the name. That is the same rule the test-only
triage Step had to adopt, and the second time in this campaign that a name match alone
would have produced the wrong answer.

Three failures in the registry schema suite are pre-existing, proven by A/B against copies
of both unmodified modules and the five unmodified tests: 3 failed and 364 passed
identically with and without this change.

## Notes on the second pass

`domain/calculations` fell from 106 exact findings to 90 across two passes. The remainder
is classified rather than deleted, and the classification is the deliverable: this area's
findings are not one population.

`live_parity` and `record_design_coverage` are production-reachable modules, not dead ones
-- `entrypoints/cli/registry.py` imports live_parity's types and `_validate_completeness`
imports record_design_coverage. What the audit flags in them is their AUDIT SURFACE, the
functions `dev/registry/parity/maintenance.py`, the analysis census, the dev conftest and
the packaging cohort script consume. Relocating individual functions out of a
production-reachable module into `dev/` would split a cohesive module and force `dev/` to
restate registry knowledge, so that surface is recorded as design-time authority and stays
where it is. The same applies to `authority.py`'s `bundled_revision_inspection`,
`stamp_bundled_registry_release` and `reset_registry_caches`.

One symbol was genuinely dead and removed: `_RegistryFingerprints`, a type alias appearing
exactly once tree-wide -- its own definition -- among three siblings declared beside it
that are used two to three times each in the same module.

Three are recorded `should-be-live` with their remedy needing a decision:
`pre_flight_oracle_operations`, `evaluate_planned_operations` and
`resolve_cross_reference_oracle`. Two are exported in `live_parity`'s `__all__`, none is
called anywhere in production or `dev/`, and each carries a substantial test suite of nine,
five and thirteen references. They are the oracle pre-flight surface for the sede
renta-web-open cluster, which this campaign already carries as unreachable staged
capability, so they are most likely transitively dead through it. Deleting exported API
from filing-grade registry code on the audit's say-so is exactly what the governing
decision reserves for its owner.

Eight failures in the wider registry selection are pre-existing, proven by A/B against a
copy of the unmodified `authority.py`: 8 failed, 506 passed and 1 skipped identically with
and without this change.
