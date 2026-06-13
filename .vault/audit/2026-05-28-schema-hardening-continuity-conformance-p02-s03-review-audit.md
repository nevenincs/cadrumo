---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-05-28-schema-hardening-continuity-conformance-plan]]'
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-adr]]'
---

# `schema-hardening` Code Review

Reviewed P02.S03 strict continuity regression tests.

No CRITICAL, HIGH, MEDIUM, or LOW findings against the authored tests.

Checks reviewed:

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_validate_cross_revision.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q -k "strict_continuity_validation_accepts_repurposed_decision or strict_continuity_validation_requires_retired_decision_for_missing_surface or strict_continuity_validation_accepts_retired_decision_for_missing_surface or strict_continuity_validation_rejects_unmatched_evolution_continuity_id or strict_continuity_validation_rejects_retired_decision_when_target_surface_remains"`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`

Review notes:

- The tests exercise the public registry-scope validation path over real schema
  models.
- The assertions inspect emitted failure messages instead of reimplementing the
  validator logic.
- The suite keeps the authored behavior generic; no test introduces a
  modelo-specific validator branch.
