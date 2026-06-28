---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S03'
related:
  - '[[2026-05-28-schema-hardening-continuity-conformance-plan]]'
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-adr]]'
---

# `schema-hardening` `P02.S03`

Added real-behavior regression tests for retired, repurposed, and unmatched
strict continuity decisions.

- Modified: `src/aeat/domain/calculations/registry/test_cross_revision_drift.py`
- Created: `.vault/exec/2026-05-28-schema-hardening-continuity-conformance/2026-05-28-schema-hardening-continuity-conformance-P02-S03.md`
- Created: `.vault/audit/2026-05-28-schema-hardening-continuity-conformance-p02-s03-review.md`

## Description

Added tests that instantiate real `ModeloDefinition`, `ModeloRevision`, and
`CasillaDefinition` objects and execute the registry-scope validator. The new
coverage proves that `repurposed` decisions cover otherwise incompatible drift,
that missing continuity surfaces require a `retired` evolution in strict
adjacent revision boundaries, that valid retired declarations pass, and that
unmatched or contradictory retired declarations fail with explicit validator
messages.

The tests do not use fakes, stubs, monkeypatches, skips, xfails, or mirrored
business logic.

## Tests

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_validate_cross_revision.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q -k "strict_continuity_validation_accepts_repurposed_decision or strict_continuity_validation_requires_retired_decision_for_missing_surface or strict_continuity_validation_accepts_retired_decision_for_missing_surface or strict_continuity_validation_rejects_unmatched_evolution_continuity_id or strict_continuity_validation_rejects_retired_decision_when_target_surface_remains"`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`

Ruff passed. The five new focused tests passed. The full cross-revision drift
suite passed with 34 tests and the existing M347 semantic-role singleton
warnings.

## Notes

The first full-suite rerun hit the tool timeout before reporting a result. The
suite was rerun with a larger timeout and passed.
