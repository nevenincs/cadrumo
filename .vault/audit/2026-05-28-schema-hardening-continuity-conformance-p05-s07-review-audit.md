---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-schema-hardening-continuity-conformance-plan]]'
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-adr]]'
  - '[[2026-05-19-modelo-registry-fragment-architecture-adr]]'
---



# `schema-hardening` Code Review

Reviewed P05.S07 governing ADR comments.

No CRITICAL, HIGH, MEDIUM, or LOW findings against the authored comment
changes.

Scope reviewed:

- `src/aeat/domain/calculations/registry/_loader.py`
- `src/aeat/domain/calculations/registry/_validate_cross_revision.py`
- `src/aeat/domain/calculations/registry/_validate_registry_scope.py`

Checks reviewed:

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_loader.py src/aeat/domain/calculations/registry/_validate_cross_revision.py src/aeat/domain/calculations/registry/_validate_registry_scope.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`

Residual note: the cross-revision pytest run failed on unrelated M210
user-profile binding WIP in the shared worktree. The authored comment changes
do not affect M210 binding selectors or user-profile schema declaration.
