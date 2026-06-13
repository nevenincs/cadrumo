---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S09'
related:
  - '[[2026-05-28-schema-hardening-continuity-conformance-plan]]'
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-adr]]'
  - '[[2026-05-19-modelo-registry-fragment-architecture-adr]]'
---



# `schema-hardening` `P05.S09`

Recorded rollout evidence for the ADR-language and governing-comment pass.

- Modified: `.vault/plan/2026-05-28-schema-hardening-continuity-conformance-plan.md`
- Created: `.vault/audit/2026-05-28-schema-hardening-continuity-conformance-p05-s09-review.md`

## Description

P05 tightened the accepted continuity ADR and added governing ADR comments to
the clean loader and validator implementation files. The code comments now
point maintainers to the fragment architecture ADR for authoring-layout
compilation and the continuity ADR D2/D3 rules for evolution records and
surface-scoped strictness.

The pass intentionally did not edit `src/aeat/domain/calculations/registry/_schema.py`
or `src/aeat/domain/calculations/registry/__init__.py` because those files had
pre-existing shared-worktree WIP.

## Tests

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_loader.py src/aeat/domain/calculations/registry/_validate_cross_revision.py src/aeat/domain/calculations/registry/_validate_registry_scope.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`
- `uv run --no-sync vaultspec-core vault check frontmatter --feature schema-hardening`
- `uv run --no-sync vaultspec-core vault check body-links --feature schema-hardening`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-28-schema-hardening-continuity-conformance-plan.md`

Ruff, loader-directory pytest, and vault checks passed. Cross-revision pytest
failed on unrelated shared-worktree M210 binding WIP:
`m210-2025-profile-country-of-fiscal-residence` currently references an
undeclared user-profile schema selector. This is a blocking signal for full
registry-suite confidence, but it is not authored by the P05 ADR/comment pass.
