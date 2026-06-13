---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m100-revision-drift-research]]'
---



# `schema-hardening` `non-overlap-drift-inventory`

Added a generic advisory inventory for repeated-casilla drift across
non-overlapping revision windows.

## Description

The strict cross-revision validator remains unchanged in intent: repeated
casilla ids that drift across overlapping revision windows are load-time
errors. Non-overlapping annual forms can legally evolve or repurpose repeated
numeric ids, so the new advisory surface reports that drift without converting
it into a hard registry-load failure.

The inventory groups findings by modelo, revision pair, field, count, and
example casilla ids. The committed-corpus test proves the current M100 annual
drift remains visible through the generic report.

## Tests

`uv run --no-sync ruff check src/aeat/domain/calculations/registry/_validate_cross_revision.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py`

Result: passed.

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`

Result: 19 passed.
