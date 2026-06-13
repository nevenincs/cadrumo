---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S07'
related:
  - '[[2026-05-28-schema-hardening-continuity-conformance-plan]]'
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-adr]]'
  - '[[2026-05-19-modelo-registry-fragment-architecture-adr]]'
---



# `schema-hardening` `P05.S07`

Added governing ADR comments to clean continuity loader and validator modules.

- Modified: `src/aeat/domain/calculations/registry/_loader.py`
- Modified: `src/aeat/domain/calculations/registry/_validate_cross_revision.py`
- Modified: `src/aeat/domain/calculations/registry/_validate_registry_scope.py`
- Created: `.vault/audit/2026-05-28-schema-hardening-continuity-conformance-p05-s07-review.md`

## Description

Marked the generic fragment append path with the governing fragment
architecture ADR and continuity ADR D2. Marked strict continuity validation and
registry-scope wiring with continuity ADR D3, including the clarified rule that
strict continuity is scoped to declared surfaces and must not infer continuity
from repeated numeric casilla ids alone.

Did not edit `src/aeat/domain/calculations/registry/_schema.py` or
`src/aeat/domain/calculations/registry/__init__.py` because those files carried
pre-existing shared-worktree WIP.

## Tests

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_loader.py src/aeat/domain/calculations/registry/_validate_cross_revision.py src/aeat/domain/calculations/registry/_validate_registry_scope.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`

The ruff check and loader-directory pytest passed. The cross-revision pytest
run failed on pre-existing shared-worktree M210 binding WIP:
`m210-2025-profile-country-of-fiscal-residence` points at
`TaxpayerTypeProfile.country_of_fiscal_residence`, which the user-profile
schema validator does not currently declare. That failure is unrelated to the
comment-only changes in this Step and is recorded rather than swallowed.
