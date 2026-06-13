---
name: data-storage-plan
description: Implementation plan for aeat#10 — SQLite+SQLAlchemy+Alembic storage layer with pydantic public records.
tags:
  - "#plan"
  - "#data-storage"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-data-storage-adr]]"
  - "[[2026-04-12-data-storage-research]]"
---

# data-storage plan

Implements `[[2026-04-12-data-storage-adr]]`. Scope is strictly issue wgergely/aeat#10.

## phase 1 — dependencies and settings

- `pyproject.toml`: add `sqlalchemy>=2.0.36` and `alembic>=1.14.0` to `dependencies`.
  Add `sqlalchemy` to `tool.ty.analysis.allowed-unresolved-imports` only if
  `ty` struggles (fall-through; prefer real type stubs).
- `src/aeat/config.py`: add three additive fields — `aeat_database_url` (default
  `sqlite:///<PROJECT_ROOT>/var/aeat.db`, serialised as string), `aeat_storage_auto_migrate`
  (bool, default `False`), `aeat_storage_backup_dir` (`Path`, default
  `<PROJECT_ROOT>/var/backups`).
- `env/.env.example`: mirror the three new fields with commented explanations.
- `tests/test_config.py` already enforces alignment and must stay green without edit.

## phase 2 — storage subpackage

All files under `src/aeat/adapters/persistence/storage/`:

- `errors.py` — `StorageError(AeatError)` plus `MigrationError` and `RepositoryError`
  subclasses. Google-style docstrings.
- `_orm.py` — **internal** SQLAlchemy 2.x declarative base + mapper classes for
  `modelos`, `portals`, `corpus_artifacts`. Uses `DeclarativeBase` +
  `Mapped[...]` + `mapped_column(...)`. Translatable columns are plain `str` with
  `# TODO(#20): replace with Translatable once i18n primitive lands`.
- `records.py` — **public** pydantic v2 record models: `ModeloRecord`,
  `PortalRecord`, `CorpusArtifactRecord`, plus `PortalAuthMethod` StrEnum. All
  records are `strict=True, frozen=True`. Include `from_orm` / `to_orm` helpers
  that take/return the internal mapper classes but do not leak them via typing.
- `engine.py` — `create_engine_from_settings(settings)` returns a SQLAlchemy
  `Engine`. Uses `sqlite:///` with `future=True`. Creates the parent directory of
  the sqlite file lazily. Public helpers: `get_engine()` (lazy singleton keyed by
  URL) and `dispose_engine()` for tests.
- `session.py` — `session_scope()` context manager (unit-of-work: commit on
  success, rollback on exception, always close). Public `get_sessionmaker()`.
- `repository.py` — `Repository[RecordT]` ABC with `list`, `get`, `upsert`,
  `delete` typed against the pydantic record type. Concrete
  `ModeloRepository`, `PortalRepository`, `CorpusArtifactRepository` classes
  that bridge via the internal ORM classes.
- `migrations_api.py` — thin public wrapper: `upgrade_to_head(engine)` and
  `round_trip_migrations(engine)` calling Alembic programmatically. This keeps
  callers (CLI, tests) out of Alembic's private API.
- `__init__.py` — re-exports the public surface only: records, enums, errors,
  `get_engine`, `dispose_engine`, `session_scope`, repositories, `upgrade_to_head`,
  `round_trip_migrations`.

## phase 3 — alembic scaffolding

Top-level `migrations/` directory:

- `alembic.ini` at the repo root. `script_location = migrations`. `sqlalchemy.url`
  is left empty and injected at runtime from `Settings.aeat_database_url`.
- `migrations/env.py` — standard Alembic env.py tailored for SQLAlchemy 2.x. Loads
  `Settings`, reads `aeat_database_url`, imports `aeat.adapters.persistence.storage._orm.metadata` as
  `target_metadata`, and uses `aeat.core.logging.get_logger` for its logger calls.
- `migrations/script.py.mako` — standard template.
- `migrations/versions/0001_initial.py` — the first revision that creates
  `modelos`, `portals`, `corpus_artifacts`. Hand-written (no autogen noise),
  symmetric `upgrade`/`downgrade`.

## phase 4 — justfile recipes

Two additive recipes, cross-platform with `[unix]` and `[windows]` variants:

- `db-migrate message`: `uv run alembic revision --autogenerate -m "{{message}}"`.
- `db-upgrade`: `uv run alembic upgrade head`.

No existing recipes touched.

## phase 5 — tests

All colocated under `src/aeat/adapters/persistence/storage/` with `@pytest.mark.unit` markers. No
mocks/patches/fakes/stubs. Inline fixtures (no reliance on `src/aeat/domain/testing/`
which is owned by #14).

- `_test_engine.py` — engine factory composes a URL, writes to a tmp sqlite file,
  round-trips a trivial raw SQL query.
- `_test_session.py` — `session_scope()` commits on success, rolls back on
  exception, and closes the session in both cases.
- `_test_repository.py` — upsert+get+list+delete round trip for each of the
  three repositories against an in-memory/tmp sqlite. Asserts repository returns
  pydantic records, not ORM rows.
- `_test_records.py` — pydantic strictness: invalid payloads raise
  `ValidationError`; records are frozen (immutability test).
- `_test_migrations.py` — **round-trip**: apply `upgrade head`, then `downgrade
  base`, then `upgrade head` again on a fresh tmp sqlite file. Then insert a row
  via the ORM to confirm tables exist.

## phase 6 — docs

Evolution workflow lives in the ADR (§ "evolution workflow"). No standalone vault
reference doc is added — the ADR is canonical. CLAUDE.md is **not** edited because
the `migrations/` top-level directory is a convention the ADR records, and CLAUDE.md
already defers to ADRs for layout decisions.

## phase 7 — verification

- `just lint` — ruff clean.
- `just typecheck` — ty clean.
- `just test` — all existing and new tests pass.
- `just hooks` — prek hooks green on modified files.

## explicit plan self-review

Cross-checked against CLAUDE.md, issue #10 acceptance criteria, vaultspec rules,
sibling branch territories, and the pydantic-mandate memory.

- **CLAUDE.md — public API discipline**: covered. Only `aeat.adapters.persistence.storage.__init__`
  re-exports; ORM internals live in `_orm.py` (leading underscore convention).
- **CLAUDE.md — Google-style docstrings + full type hints**: every public symbol
  gets one during phase 2.
- **CLAUDE.md — errors inherit from `AeatError`**: `StorageError` subclasses
  `AeatError`, everything else subclasses `StorageError`.
- **CLAUDE.md — logging via `get_logger`**: all modules including Alembic env.py.
- **CLAUDE.md — pytest only, `@pytest.mark.unit` colocated**: yes. No unittest.
  No mocks/patches/stubs/fakes anywhere.
- **CLAUDE.md — config test alignment**: phase 1 adds three fields to both
  `Settings` and `env/.env.example`. `tests/test_config.py` requires no edit.
- **Pydantic mandate memory**: the public surface is pydantic v2 records with
  `strict=True, frozen=True`; ORM mapper classes are *internal only* and never
  leak. No bare `dict[str, Any]` in any public signature.
- **Sibling #14 (`tests/fixtures/filing_history/`, `src/aeat/domain/testing/`)**: not
  touched; storage tests use inline fixtures.
- **Sibling #15 (pytest config)**: not touched.
- **Sibling #16 (`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/`)**: not touched.
- **Sibling #20 (trilingual primitives)**: translatable columns are plain `str`
  today with inline `TODO(#20)` markers. No competing translation type defined.
- **Issue #10 acceptance**:
  - research + ADR + plan + exec artefacts — yes.
  - `src/aeat/adapters/persistence/storage/` connection factory, session helpers, base, errors — yes.
  - Alembic under `migrations/` + initial revision + `just db-migrate` +
    `just db-upgrade` — yes.
  - first-cut `modelos` / `portals` / `corpus_artifacts` with translatable
    stubs — yes.
  - settings additions + `.env.example` alignment — yes.
  - migration round-trip test — yes.
  - documented evolution workflow — yes (ADR § evolution workflow).
  - `just lint && just typecheck && just test && just hooks` all green locally —
    required before commit per phase 7.
- **Out of scope guardrails**: no table population, no web UI, no multi-tenancy,
  no trilingual primitives, no historical backfill, no mocks in tests, no
  contamination of sibling branches' territories.

Review outcome: plan approved for execution.
