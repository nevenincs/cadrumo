---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-schema-hardening-continuity-conformance-plan]]'
  - '[[2026-05-28-schema-hardening-continuity-conformance-research]]'
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-adr]]'
---



# `schema-hardening` Code Review

Reviewed P01.S01 continuity conformance audit.

No CRITICAL, HIGH, MEDIUM, or LOW findings against the Step execution.

The research correctly records one material implementation gap for follow-up:
current strict continuity validation is declared-surface scoped, while the
accepted ADR D3 text describes full repeated-id drift declaration after opt-in.
That is a planned-work finding, not a defect in this audit artifact.

Checks reviewed:

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_validate_cross_revision.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`

Residual note: the pytest run passed with existing M347 singleton
semantic-role warnings.
