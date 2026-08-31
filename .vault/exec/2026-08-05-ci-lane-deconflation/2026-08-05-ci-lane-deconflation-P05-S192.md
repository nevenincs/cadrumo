---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:70e7ddc65fd3109ec8af1878153a7a7788434538b3207c7575b4f32a7bc05b3f'
step_id: 'S192'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in schema.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/domain/calculations/registry/schema.py`

## Changes

- `M` `dev/registry/authoring_migrate_applicability_fragments.py`
- `M` `src/cadrumo/application/overview/calendar.py`
- `M` `src/cadrumo/application/overview/explain.py`
- `M` `src/cadrumo/domain/calculations/registry/_validate_dependency_sections.py`
- `M` `src/cadrumo/domain/calculations/registry/_validate_official_source_guidance_content.py`
- `M` `src/cadrumo/domain/calculations/registry/_validate_revision_context.py`
- `M` `src/cadrumo/domain/calculations/registry/_validate_revision_rules.py`
- `M` `src/cadrumo/domain/calculations/registry/applicability.py`
- `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `M` `src/cadrumo/domain/calculations/registry/deadline_coordinate.py`
- `M` `src/cadrumo/domain/calculations/registry/handoffs.py`
- `M` `src/cadrumo/domain/calculations/registry/schedules.py`
- `M` `src/cadrumo/domain/calculations/registry/schema.py`
- `A` `src/cadrumo/domain/calculations/registry/schema_deadlines.py`
- `A` `src/cadrumo/domain/calculations/registry/schema_revision_members.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/_referential_integrity_support.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_applicability_fragment_family.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_classification_coherence.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_construct_closure_validator_call_sites.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_cross_dependency_contract.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_deadline_semantic_coordinate.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_deadline_window_authority_projection.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_deadline_window_ownership.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_deadline_window_qualifiers.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_deadline_window_uniqueness.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_180_registry.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_referential_integrity_part4.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_registry_schema_part2.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_schema.py`
- `M` `src/cadrumo/domain/deadlines/engine.py`
- `M` `src/cadrumo/domain/deadlines/plazo.py`
- `M` `src/cadrumo/domain/deadlines/tests/test_plazo_resolution.py`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S192.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p05-s192-execution-self-review-audit.md`
- `verify:` `uv run --no-sync python -c "import cadrumo.domain.calculations.registry.schema as schema; assert not hasattr(schema, 'ApplicationLinkDefinition'); assert not hasattr(schema, 'DeadlineWindowDefinition'); from cadrumo.domain.calculations.registry.schema_revision_members import ApplicationLinkDefinition; from cadrumo.domain.calculations.registry.schema_deadlines import DeadlineWindowDefinition; print('direct-boundary-ok')"` -> `direct-boundary-ok`

## Notes

- Immutable source commit `945987e7cd8530f4484073b82ebc576d0d715478` has exactly the 32 source paths logged above. It changes no threshold or size baseline. Raw saved-blob physical counts are `schema.py` 1185, `schema_revision_members.py` 211, and `schema_deadlines.py` 161, each within the 1250 ceiling.
- The executor reported `ruff check` plus format and `py_compile` clean, and reported its focused suite as `83 passed in 2.76s`; no literal terminal command was retained, so this is reported evidence rather than a reconstructed receipt. The direct-boundary assertion above was run by root post-commit and printed `direct-boundary-ok`.
- The executor also reported 59 unrelated global audit findings with schema absent; this is a module-specific conclusion, not a global-green claim. Earlier 35 registry-schema and 9 deadline-resolver passes are not used as receipts here.
