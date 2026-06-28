---
name: data-storage-phase1-summary
description: Execution summary for aeat#10 — SQLite+SQLAlchemy+Alembic storage layer.
tags:
  - "#exec"
  - "#data-storage"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-data-storage-plan]]"
  - "[[2026-04-12-data-storage-adr]]"
  - "[[2026-04-12-data-storage-research]]"
---

# data-storage phase1 summary

## scope delivered

Single-pass execution of `[[2026-04-12-data-storage-plan]]`. All phases
landed in one commit on branch `feature/10-data-storage`.

### dependencies + settings

- `pyproject.toml`: added `sqlalchemy>=2.0.36`, `alembic>=1.14.0`.
- `src/aeat/config.py`: added `aeat_database_url`, `aeat_storage_auto_migrate`,
  `aeat_storage_backup_dir`.
- `env/.env.example`: mirrored the three new fields with commented defaults.
- `tests/test_config.py` alignment stayed green without edit.

### storage subpackage (`src/aeat/adapters/persistence/storage/`)

- `errors.py` — `StorageError(AeatError)`, `MigrationError`, `RepositoryError`.
- `_orm.py` — internal SQLAlchemy 2.x declarative base and mappers for
  `modelos`, `portals`, `corpus_artifacts`. Translatable columns carry
  `TODO(#20)` markers.
- `records.py` — pydantic v2 public records (`strict=True, frozen=True`) +
  `PortalAuthMethod` StrEnum.
- `engine.py` — URL-keyed singleton engine factory with lazy parent-directory
  creation for SQLite files.
- `session.py` — `session_scope()` context manager with commit/rollback/close
  semantics, plus `get_sessionmaker()`.
- `repository.py` — PEP-695 `Repository[RecordT]` ABC and concrete
  `ModeloRepository`, `PortalRepository`, `CorpusArtifactRepository`.
- `migrations_api.py` — programmatic Alembic facade (`upgrade_to_head`,
  `downgrade_to_base`, `round_trip_migrations`).
- `__init__.py` — narrow public re-export surface.

### alembic scaffolding

- `alembic.ini` at the repo root with `path_separator = os` and a blank
  `sqlalchemy.url` (injected at runtime).
- `migrations/env.py` — pulls URL from `Settings` when not injected; uses
  `aeat.core.logging.get_logger`.
- `migrations/script.py.mako` — SQLAlchemy 2.x-style template.
- `migrations/versions/0001_initial.py` — hand-written initial revision
  creating the three tables with symmetric upgrade/downgrade.

### justfile

- `db-migrate message="..."` and `db-upgrade` recipes, cross-platform
  (`[unix]` + `[windows]` variants).

### tests (colocated, `@pytest.mark.unit`, no mocks)

- `_test_engine.py` — SQL round-trip, parent-dir creation, empty-URL rejection.
- `_test_session.py` — commit on success, rollback on exception.
- `_test_records.py` — strict mode refuses coercion; frozen records reject
  mutation; sha256 length enforced.
- `_test_repository.py` — CRUD round trip per repository, enum round trip.
- `_test_migrations.py` — `upgrade head → downgrade base → upgrade head`
  against a fresh tmp SQLite file, followed by a live insert.
- `test_smoke.py` — updated to assert the expanded public surface.

## verification

```
just lint      → clean
just typecheck → clean
just test      → 111 passed, 1 skipped, 6 deselected
just hooks     → all hooks passed
```

## deviations from plan

- `Repository[RecordT]` uses PEP-695 generic syntax (`class
  Repository[RecordT](ABC)`) instead of `Generic[RecordT]` after ruff UP046
  flagged the latter. Behaviour unchanged.
- The abstract list method is named `list_all` (not `list`) because ty rejects
  `list[RecordT]` return annotations when a method named `list` shadows the
  builtin. Renaming is a clearer API anyway.

## follow-ups (explicitly not in scope)

- Populate tables (#6, #7, #17, #23).
- Sheets/Drive export adapter (deferred by ADR).
- Filing history table (#14).
- Schema versioning tables (#9).
- Trilingual storage shape (#20) — `TODO(#20)` markers in place on every
  translatable column and record field.
