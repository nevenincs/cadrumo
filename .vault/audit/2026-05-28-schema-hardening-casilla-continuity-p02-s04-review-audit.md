---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-plan]]'
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-adr]]'
---



# `schema-hardening` Code Review

Reviewed P02.S04 implementation for continuity-aware cross-revision advisory
drift analysis.

No CRITICAL, HIGH, MEDIUM, or LOW findings.

Scope reviewed:

- `src/aeat/domain/calculations/registry/_validate_cross_revision.py`
- `src/aeat/domain/calculations/registry/test_cross_revision_drift.py`

Checks reviewed:

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_validate_cross_revision.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`

Residual note: the test run passed but emitted four pre-existing singleton
semantic-role warnings for M347 during committed-corpus validation.
