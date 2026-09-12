---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:91fb8c4a5e9495e35b0a556d26647b48301ef466179ab3a2ba5c0f2a0950b5f4'
step_id: 'S23'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Migrate persisted CalculationRevision.relation_overrides to binding-id keys through a forward, idempotent stored-data migration driven by a frozen relation-to-binding table, recompute affected revision ids and record the old-to-new pairs, with tests from every supported stored version

## Scope

- `src/cadrumo/domain/modelos/calculation_revision.py`
- `src/cadrumo/domain/modelos/calculation_revision_identity.py`
- `src/cadrumo/adapters/persistence/`

## Changes

- `A` `src/cadrumo/adapters/persistence/profile/relation_binding_join.json`
- `A` `src/cadrumo/adapters/persistence/profile/relation_binding_join.py`
- `A` `src/cadrumo/adapters/persistence/profile/calculation_revision_override_migration.py`
- `A` `src/cadrumo/adapters/persistence/profile/tests/test_calculation_revision_override_migration.py`
- `A` `src/cadrumo/application/modelo/tests/test_orphaned_override_diagnostic.py`
- `M` `src/cadrumo/application/aggregation/source_mesh.py`
- `M` `src/cadrumo/application/modelo/calculation_actions.py`
- `M` `src/cadrumo/core/errors/registry/_application_part2.py`
- `verify:` `uv run pytest src/cadrumo/adapters/persistence/profile/tests/test_calculation_revision_override_migration.py -n 0` -> `pass`
- `verify:` `uv run ruff check` on touched files -> `pass`
- `verify:` `uv run ty check` on touched files -> `pass`
- `verify:` `uv run basedpyright` on touched files -> `pass`

## Notes

The persisted field name `relation_overrides` and the runtime channels
`relation_values` / `unresolved_relation_ids` were NOT renamed: the rename spans
33 production modules (154 including tests), above the threshold set for this
Step. The naming is retained debt.

`src/cadrumo/application/modelo/tests/test_orphaned_override_diagnostic.py` could
not be executed: the `application/modelo/tests` conftest fails to import at HEAD
(`m303_carry_header_key` absent from `application/calculations/m303_carry_ingress.py`),
a pre-existing breakage unrelated to this Step. Its three assertions were verified
by direct invocation instead.

`src/cadrumo/domain/modelos/tests/test_calculation_revision_evidence.py::test_revision_id_pinned_across_every_optional_branch`
fails at HEAD with a shifted pinned hash; no identity input was touched here.
