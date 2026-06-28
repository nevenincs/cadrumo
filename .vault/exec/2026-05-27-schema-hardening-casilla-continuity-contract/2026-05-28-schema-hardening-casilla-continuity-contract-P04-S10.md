---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S10'
related:
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-plan]]'
  - '[[2026-05-28-schema-hardening-m100-continuity-inventory-research]]'
---



# `schema-hardening` `P04.S10`

Added committed-corpus regression gates for the M100 continuity surface.

- Modified: `src/aeat/domain/calculations/registry/test_cross_revision_drift.py`
- Created: `.vault/audit/2026-05-28-schema-hardening-casilla-continuity-p04-s10-review.md`

## Description

Added a committed-corpus gate that verifies M100 revisions `2022` through
`2025` load with strict continuity mode and the `0582` continuity id. Added a
mutation gate that changes the committed 2025 `0582` label inside the full
loaded registry corpus and asserts strict continuity validation fails for the
covered source revisions.

The mutation uses real registry models loaded from disk and `model_copy`;
it does not patch loader or validator behavior.

## Tests

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/test_cross_revision_drift.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_committed_m100_continuity_surface_for_0582_is_loaded src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_committed_m100_strict_continuity_surface_rejects_covered_label_drift src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_backend_registry_validation_accepts_committed_corpus_drift_gate -q`

The pytest run passed with existing M347 singleton semantic-role warnings.
