---
tags:
  - '#exec'
  - '#registry-drift-validator-blocking-gap'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S04'
related:
  - '[[2026-06-04-registry-drift-validator-blocking-gap-plan]]'
---

# S04 - Verify drift-validator blocking-gap gates

Plan: `.vault/plan/2026-06-04-registry-drift-validator-blocking-gap-plan.md`
Step: S04
Status: complete

## Gates

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_validate_semantic_role_typos.py src/aeat/domain/calculations/registry/_validate_semantic_roles.py src/aeat/domain/calculations/registry/_validate_registry_scope.py src/aeat/domain/calculations/registry/test_semantic_role.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/calculations/registry/test_registry_reviewability.py src/aeat/domain/calculations/registry/test_committed_registry.py`
  - Result: passed.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_semantic_role.py -q`
  - Result: 37 passed.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_reviewability.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
  - Result: 30 passed.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_backend_registry_validation_accepts_committed_corpus_drift_gate src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_singleton_semantic_role_warning_count_does_not_regress -q`
  - Result: 2 passed.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_committed_registry.py -q`
  - Result: 41 passed.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-06-04-registry-drift-validator-blocking-gap-plan.md`
  - Result: passed.

## Result

The post-commit verification suite confirms:

- the synthetic typo-twin mutation now blocks registry scope;
- the committed corpus remains clean;
- directory-mode loader behavior remains intact;
- reviewability line-count and row-width guards remain green.
