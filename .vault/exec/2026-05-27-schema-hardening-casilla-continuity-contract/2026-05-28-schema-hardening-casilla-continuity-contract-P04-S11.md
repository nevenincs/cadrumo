---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S11'
related:
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-plan]]'
  - '[[2026-05-28-schema-hardening-m100-continuity-inventory-research]]'
---



# `schema-hardening` `P04.S11`

Recorded closeout evidence for the continuity contract rollout and cleaned the
registry package lint surface required by the plan verification gate.

- Modified: `src/aeat/domain/calculations/registry`
- Created: `.vault/audit/2026-05-28-schema-hardening-casilla-continuity-p04-s11-review.md`
- Created: `.vault/exec/2026-05-27-schema-hardening-casilla-continuity-contract/2026-05-28-schema-hardening-casilla-continuity-contract-P04-summary.md`

## Description

Closed the plan evidence loop after the continuity substrate, loader fragment
support, advisory drift report annotations, opt-in strict continuity validation,
and first M100 strict continuity surface were already committed.

The final package lint gate found pre-existing registry-package style failures
outside the continuity files. Those were repaired mechanically as part of this
closeout so the declared verification command can run against the package
surface instead of a narrower subset.

Remaining blockers are intentionally outside this plan:

- M100 has one strict continuity surface, `0582`, covering the 2022 through
  2025 chain; broader M100 rollout remains incremental evidence work.
- Annual M100 drift outside declared continuity ids remains advisory until each
  surface is authored with evidence.
- Template expansion and any M100 template compiler remain out of scope.
- Existing M347 singleton semantic-role warnings still appear during committed
  corpus validation and should be handled by the semantic-role cleanup track.

## Tests

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_committed_registry.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_public_api_boundaries.py -q`
- `uv run --no-sync vaultspec-core vault check frontmatter --feature schema-hardening`
- `uv run --no-sync vaultspec-core vault check body-links --feature schema-hardening`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-27-schema-hardening-casilla-continuity-contract-plan.md`

All commands passed. The cross-revision pytest run emitted the existing M347
singleton semantic-role warnings.
