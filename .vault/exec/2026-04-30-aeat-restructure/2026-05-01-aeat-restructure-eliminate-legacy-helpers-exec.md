---
tags:
  - '#exec'
  - '#aeat-restructure'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-summary-exec]]"
---

# `aeat-restructure` `eliminate-shims` `delete-legacy-migration-helpers`

Deleted all 5 `migrate_legacy_*_to_repository` helpers and their companion
`*MigrationSummary` pydantic models. Removed corresponding test classes from
the 5 co-located test files. Updated `alembic.ini` comment. Audited
`migrations/env.py` and all 3 revision files — no changes required.

- Modified: `src/aeat/adapters/outbound/aeat/export/_repository.py`
- Modified: `src/aeat/adapters/outbound/aeat/export/_test_repository.py`
- Modified: `src/aeat/application/filing/_complementaria_repository.py`
- Modified: `src/aeat/application/filing/_test_complementaria_repository.py`
- Modified: `src/aeat/application/filing/_history_repository.py`
- Modified: `src/aeat/application/filing/_test_history_repository.py`
- Modified: `src/aeat/application/filing/_repository.py`
- Modified: `src/aeat/application/filing/_test_repository.py`
- Modified: `src/aeat/domain/justificante/_repository.py`
- Modified: `src/aeat/domain/justificante/_test_repository.py`
- Modified: `alembic.ini`

## Description

### migrations audit

`migrations/env.py` imports are already canonical:
- `aeat.core.config.load_settings` (via `load_settings`)
- `aeat.adapters.persistence.storage._orm` (metadata)
- `aeat.adapters.persistence.storage.engine._ensure_sqlite_parent`
- `aeat.core.logging.get_logger`

No changes needed to `env.py`.

Three revision files (`0001_initial`, `0002_constraints`, `0003_rental_register`)
have no Python imports — all DDL is expressed through sqlalchemy ops. No stale
table references. No squash candidates (each revision is self-contained and
touches different concerns).

`alembic.ini` corrected the comment reference from `aeat.config.Settings` to
`aeat.core.config.Settings`.

### legacy helper deletion

Five helpers were removed from 5 repository modules:
- `migrate_legacy_submissions_to_repository` + `SubmissionMigrationSummary`
- `migrate_legacy_amendments_to_repository` + `AmendmentMigrationSummary`
- `migrate_legacy_filing_history_to_repository` + `HistoryMigrationSummary`
- `migrate_legacy_drafts_to_repository` + `DraftMigrationSummary`
- `migrate_legacy_justificantes_to_repository` + `JustificanteMigrationSummary`

No production callers existed outside the helpers' own test files. All
`__all__` exports and unused pydantic imports were cleaned up. Issue #477
closed with deletion comment.

## Tests

87 unit tests pass across the 5 affected test files after removal. `ruff check`
reports zero errors; `ruff format` reformatted 5 source files (double blank line
cleanup from block removal). `alembic check` exits with expected
`Target database is not up to date` (no regression — no migration DB in the
worktree environment).
