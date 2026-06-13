---
name: data-storage-adr
description: Adopt SQLite + SQLAlchemy 2.x + Alembic as the primary persistence backend for aeat.
tags:
  - "#adr"
  - "#data-storage"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-data-storage-research]]"
  - "[[2026-04-12-data-storage-plan]]"
  - "[[2026-04-12-base-module-structure-adr]]"
---

# data-storage adr

## status

Accepted.

## context

See `[[2026-04-12-data-storage-research]]`. Issue wgergely/aeat#10 requires a single,
defensible decision on where structured state lives and how it is evolved. Five
candidate backends were surveyed against migration story, query expressiveness, type
safety, ops footprint, portability, cost, fit with a CLI-first future web phase, and
security posture. Sibling issue #20 owns the trilingual primitive and must not be
pre-empted.

## decision

1. **Primary backend**: SQLite, accessed via **SQLAlchemy 2.x** (typed mapped columns)
   with **Alembic** for migrations. Default database URL is
   `sqlite:///<project>/var/aeat.db`. The connection string is driven exclusively by
   `Settings.aeat_database_url` so switching to PostgreSQL later is a single env-var
   change plus a migration review.
2. **Migration tool**: Alembic, with migration sources under the top-level
   `migrations/` directory (alongside `alembic.ini` at the repo root). Every schema
   change ships with an explicit upgrade + downgrade revision. Auto-generation is
   allowed but every generated revision is reviewed by a human before merge.
3. **Auto-apply on startup**: disabled by default
   (`AEAT_STORAGE_AUTO_MIGRATE=false`). Migrations are applied deliberately via
   `just db-upgrade`. CI and developers run the same recipe.
4. **Public API discipline**: callers import only from `aeat.adapters.persistence.storage`. Internal
   modules (`aeat.adapters.persistence.storage.engine`, `aeat.adapters.persistence.storage.session`, `aeat.adapters.persistence.storage.base`,
   `aeat.adapters.persistence.storage.models`) are not importable from outside the subpackage per project
   convention.
5. **Type discipline** (honours the project pydantic mandate — every record that
   crosses a boundary is a pydantic v2 model):
   - SQLAlchemy ORM mapper classes live in `aeat.adapters.persistence.storage._orm` and are **internal**.
     They exist only to back the declarative schema used by Alembic autogenerate;
     they are never exported.
   - The public surface of `aeat.adapters.persistence.storage` exposes **pydantic v2** record models
     (`ModeloRecord`, `PortalRecord`, `CorpusArtifactRecord`) with
     `model_config = ConfigDict(strict=True, frozen=True)`. Repositories translate
     between the pydantic records and the internal ORM rows on both read and
     write.
   - Enums for closed catalogues (`PortalAuthMethod` here).
   - No bare `dict[str, Any]` in any public signature.
6. **Errors**: a single `StorageError(AeatError)` base in
   `src/aeat/adapters/persistence/storage/errors.py`, with narrow subclasses (`MigrationError`,
   `RepositoryError`) added only when the public API actually raises them.
7. **Logging**: `aeat.core.logging.get_logger(__name__)` in every module. Alembic's
   `env.py` forwards its loggers through the same factory.
8. **First-cut tables** (exactly the scope of issue #10):
   - `modelos` — `id` (PK surrogate), `identifier` (natural key, e.g. `MODELO_130`),
     plus `name_stub` on a translatable field that is flagged with a
     `TODO(#20)` marker referencing `[[2026-04-12-data-storage-research]]` §4. The
     real trilingual shape is owned by issue #20; storage stores strings today.
   - `portals` — `id`, `identifier`, `base_url`, `auth_method` (enum string),
     optional `modelo_id` FK.
   - `corpus_artifacts` — `id`, `year`, `modelo_id` FK, `file_path`, `sha256`,
     `source_url`, `fetched_at` (UTC). Matches the manifest shape #17 will emit.
9. **Translatable fields**: any field that will eventually hold human-language text
   is a plain `str` column today, annotated with `# TODO(#20): convert to
   Translatable once i18n primitive lands`. No competing translation type is
   defined here.
10. **Certificate bytes**: never stored in the database. `corpus_artifacts` stores
    `file_path` + `sha256` only.
11. **Export to Sheets/Drive**: explicitly deferred. The research rejected Sheets as
    a primary backend; a read-only export adapter is a later issue.

## consequences

### positive

- Zero ops: a single file under `var/aeat.db`. Backups are file copies.
- Migrations are reviewable, auto-generatable, and round-trip-testable.
- SQLAlchemy 2.x typed API aligns with the project's type-first CLAUDE.md rules.
- Swapping to Postgres later is a connection-string change, not a rewrite.
- Alembic's `env.py` is isolated behind `migrations/`, leaving the `src/aeat/`
  subpackage layout untouched.

### negative

- SQLite writer concurrency is single-threaded. Unacceptable for multi-user; we are
  not multi-user yet. When we are, the switch to Postgres is planned.
- SQLAlchemy + Alembic adds two runtime dependencies. Both are mature, typed,
  widely deployed. Acceptable.

### neutral

- DuckDB and TinyDB are closed out for this phase and can be reopened only with a
  new ADR.

## evolution workflow

1. Edit or add a declarative model under `src/aeat/adapters/persistence/storage/models.py`.
2. Run `just db-migrate message="<short description>"` to generate a revision under
   `migrations/versions/`.
3. Inspect the generated revision; adjust the `upgrade()` and `downgrade()` bodies
   as needed; ensure the downgrade is a true inverse.
4. Run the migration round-trip test (`uv run pytest
   src/aeat/adapters/persistence/storage/_test_migrations.py`). It must pass against a fresh ephemeral
   database.
5. Commit the model change and the revision together in a single commit.
6. Apply locally with `just db-upgrade`. CI/prod runs the same recipe.

## out of scope

- Populating tables — handled by #6, #7, #9, #17, #23.
- A Sheets export adapter.
- Multi-tenant auth / row-level security.
- Historical backfill.
- Trilingual storage shape (owned by #20).
