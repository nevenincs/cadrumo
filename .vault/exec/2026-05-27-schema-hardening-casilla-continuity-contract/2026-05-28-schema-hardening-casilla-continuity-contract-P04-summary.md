---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-plan]]'
  - '[[2026-05-28-schema-hardening-m100-continuity-inventory-research]]'
---



# `schema-hardening` `P04` summary

Completed the gates and closeout phase for the casilla continuity contract.

- Modified: `src/aeat/domain/calculations/registry/test_cross_revision_drift.py`
- Modified: `src/aeat/domain/calculations/registry`
- Created: `.vault/audit/2026-05-28-schema-hardening-casilla-continuity-p04-s10-review.md`
- Created: `.vault/audit/2026-05-28-schema-hardening-casilla-continuity-p04-s11-review.md`
- Created: `.vault/exec/2026-05-27-schema-hardening-casilla-continuity-contract/2026-05-28-schema-hardening-casilla-continuity-contract-P04-S10.md`
- Created: `.vault/exec/2026-05-27-schema-hardening-casilla-continuity-contract/2026-05-28-schema-hardening-casilla-continuity-contract-P04-S11.md`

## Description

P04 added committed-corpus regression tests that prove the first M100 strict
continuity surface loads and rejects a real covered label mutation. The phase
then recorded full verification evidence and package lint cleanup required by
the plan-level verification command.

The continuity substrate is generic: schema fields, directory fragment loading,
advisory report enrichment, strict validation, and public report exports are
not tied to a modelo-specific definition. The initial strict corpus adoption is
deliberately scoped to the evidence-authored M100 `0582` chain.

## Tests

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_committed_registry.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_public_api_boundaries.py -q`
- `uv run --no-sync vaultspec-core vault check frontmatter --feature schema-hardening`
- `uv run --no-sync vaultspec-core vault check body-links --feature schema-hardening`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-27-schema-hardening-casilla-continuity-contract-plan.md`

All commands passed. Existing M347 singleton semantic-role warnings remain
visible during the cross-revision committed-corpus validation tests.
