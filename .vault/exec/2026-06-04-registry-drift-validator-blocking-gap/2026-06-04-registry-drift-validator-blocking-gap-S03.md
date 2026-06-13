---
tags:
  - '#exec'
  - '#registry-drift-validator-blocking-gap'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S03'
related:
  - '[[2026-06-04-registry-drift-validator-blocking-gap-plan]]'
---

# S03 - Promote semantic-role typo twins to registry-scope failures

Plan: `.vault/plan/2026-06-04-registry-drift-validator-blocking-gap-plan.md`
Step: S03
Status: complete

## Change

- Added `grouped_semantic_role_typo_twin_failures()` in `_validate_semantic_role_typos.py` so the existing typo-twin detector has a failure-producing path as well as the diagnostic warning path.
- Threaded `_validate_semantic_role_typo_twins()` through `validate_registry_scope()`, so unreviewed singleton semantic roles that look like typo twins now become registry-scope failures and therefore surface as `RegistryValidationError` through `RegistryValidator.validate_registry()`.
- Kept `_emit_semantic_role_typo_twin_warnings()` for focused diagnostic callers and existing warning-surface tests.
- Converted the S02 synthetic mutation regression from "warns but passes" to "fails registry scope with the exact tuple".

## Verification

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_validate_semantic_role_typos.py src/aeat/domain/calculations/registry/_validate_semantic_roles.py src/aeat/domain/calculations/registry/_validate_registry_scope.py src/aeat/domain/calculations/registry/test_semantic_role.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_semantic_role.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_reviewability.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_backend_registry_validation_accepts_committed_corpus_drift_gate src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_singleton_semantic_role_warning_count_does_not_regress -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_committed_registry.py -q`

## Result

The committed corpus remains clean under the new hard-fail path. The blocking behavior is proven by a synthetic mutation test because S01 found no real current corpus singleton typo-twin drift after prior singleton metadata cleanup.
