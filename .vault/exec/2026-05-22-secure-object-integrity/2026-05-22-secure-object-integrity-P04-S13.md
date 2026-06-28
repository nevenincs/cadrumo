---
tags:
  - '#exec'
  - '#secure-object-integrity'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S13'
related:
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
---




# `secure-object-integrity` `P04.S13`

Extended relational SQL diagnostics beyond table presence to report non-secure relational column drift and foreign-key drift with sanitized finding details.

- Modified: `src/aeat/application/diagnostics.py`
- Modified: `src/aeat/application/test_diagnostics.py`
- Created: `.vault/audit/2026-05-22-secure-object-integrity-P04-S13-review.md`

## Description

The relational database integrity check now builds its expected table map from ORM metadata while explicitly excluding secure-object tables. This keeps the existing secure-object decryptability and attribution diagnostics as the owner of `secure_objects`, while S13 covers relational SQL state outside that store.

The check now validates expected columns for every non-secure relational table and returns internal-audience `DiagnosticFinding` rows for missing columns. SQLite foreign-key drift now also carries sanitized finding entries that name table, rowid, parent table, and foreign-key id without reading or printing row payload values. Clean schemas report that relational tables are present with expected columns.

Regression coverage now proves clean schema success, secure-object table absence is ignored by this relational check, non-secure missing tables still fail, missing-column drift is reported, and foreign-key findings remain sanitized.

## Tests

Focused gates passed:

- `uv run ruff check src/aeat/application/diagnostics.py src/aeat/application/test_diagnostics.py`
- `uv run pytest src/aeat/application/test_diagnostics.py -q`

Mandatory scoped review initially found one high blocker because `secure_objects` was treated as relational scope. That blocker was fixed and re-reviewed; no critical or high blockers remain.

Review audit: `2026-05-22-secure-object-integrity-P04-S13-review`.
