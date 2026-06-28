---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'W04.F20'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-20-live-iva-compensation-wallet-review-audit]]'
  - '[[2026-05-21-live-iva-compensation-wallet-code-review-audit]]'
---

# `live-iva-compensation-wallet` `W04.F20`

Added read-only relational database integrity diagnostics to the repair surface.

- Modified: `src/aeat/application/diagnostics.py`
- Modified: `src/aeat/application/test_diagnostics.py`

## Description

WALLET-063 covered both unreadable secure-object drift and relational SQL state outside `secure_objects`. Earlier repair checks could reach normal repositories before any schema inspection, which meant the SQL storage singleton could auto-create missing ORM tables and hide table-presence drift.

This step adds `relational_database.integrity` near the top of `aeat config repair`, before secure-state and secure-object probes. It creates a fresh SQLAlchemy engine from settings rather than using the auto-creating singleton, then checks:

- expected ORM table presence
- SQLite `PRAGMA integrity_check`
- SQLite `PRAGMA foreign_key_check`

The diagnostic is read-only. It does not create missing tables, mutate rows, contact AEAT, or print row payloads. Missing SQLite files are treated as first-run bootstrap only when there is no active profile. If an active profile is configured and its database file is absent, the check fails closed with an internal restore-from-backup message.

The review pass initially found that active-profile database loss could be hidden by the first-run bootstrap path. That path was corrected and covered by a regression that verifies the missing database file is not created during inspection.

No live AEAT operation was performed in this step.

## Tests

- `uv run pytest src/aeat/application/test_diagnostics.py -q --disable-warnings` completed with 29 passed.
- `uv run pytest src/aeat/application/test_diagnostics.py src/aeat/application/test_repair_integrity.py -q --disable-warnings` completed with 43 passed.
- `uv run ruff check src/aeat/application/diagnostics.py src/aeat/application/test_diagnostics.py` passed.
- `uv run aeat config repair` reported `ok relational_database.integrity 9 relational table(s) present`, with the known auth-readiness and secure-object unreadable warnings still present.
