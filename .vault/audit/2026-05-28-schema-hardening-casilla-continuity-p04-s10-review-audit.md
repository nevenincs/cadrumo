---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-plan]]'
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-adr]]'
  - '[[2026-05-28-schema-hardening-m100-continuity-inventory-research]]'
---



# `schema-hardening` Code Review

Reviewed P04.S10 committed-corpus continuity regression gates.

No CRITICAL, HIGH, MEDIUM, or LOW findings.

Scope reviewed:

- `src/aeat/domain/calculations/registry/test_cross_revision_drift.py`

Checks reviewed:

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/test_cross_revision_drift.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_committed_m100_continuity_surface_for_0582_is_loaded src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_committed_m100_strict_continuity_surface_rejects_covered_label_drift src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_backend_registry_validation_accepts_committed_corpus_drift_gate -q`

Residual note: the focused pytest run passed but emitted existing M347
singleton semantic-role warnings.
