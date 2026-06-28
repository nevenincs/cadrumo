---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S04'
related:
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-plan]]'
---



# `schema-hardening` `P02.S04`

Extended cross-revision advisory drift analysis with continuity and evolution
metadata.

- Modified: `src/aeat/domain/calculations/registry/_validate_cross_revision.py`
- Modified: `src/aeat/domain/calculations/registry/test_cross_revision_drift.py`
- Created: `.vault/audit/2026-05-28-schema-hardening-casilla-continuity-p02-s04-review.md`

## Description

Added continuity metadata to each cross-revision casilla divergence and grouped
advisory summary. The inventory now reports observed `continuidad_id` values,
declared evolution kinds, and counts of divergences covered or not covered by
the declared evolution. This is analysis-only substrate; the overlapping
revision hard validator remains unchanged, and opt-in strict enforcement is
left to the next plan step.

The cross-revision tests now build real registry schema models for new and
existing synthetic cases instead of lightweight stand-ins. Added coverage for a
label drift covered by `label_evolved` and a legal-reference drift left
uncovered by a label-only evolution declaration.

## Tests

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_validate_cross_revision.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`

The pytest run passed with four existing singleton semantic-role warnings for
M347 emitted by committed-corpus registry validation.
