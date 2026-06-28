---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S01'
related:
  - '[[2026-05-28-schema-hardening-continuity-conformance-plan]]'
  - '[[2026-05-28-schema-hardening-continuity-conformance-research]]'
---



# `schema-hardening` `P01.S01`

Audited the landed continuity substrate against ADR D1 through D5 before any
new code or corpus data rollout.

- Created: `.vault/research/2026-05-28-schema-hardening-continuity-conformance-research.md`
- Created: `.vault/audit/2026-05-28-schema-hardening-continuity-conformance-p01-s01-review.md`

## Description

Recorded implemented, partial, and gap states for the continuity schema,
directory loader, cross-revision validator, registry-scope validator, tests,
and committed M100 `0582` data slice.

The audit found that the implementation is generic and not M100-specialized,
but it also found a material D3 semantics conflict: current strict mode skips
unannotated repeated-id drift even though the accepted ADR says opt-in strict
mode must require repeated-id drift to be declared or explicitly marked
repurposed.

No source code was modified in this Step.

## Tests

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_validate_cross_revision.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`

Both commands passed. The pytest run emitted existing M347 singleton
semantic-role warnings.
