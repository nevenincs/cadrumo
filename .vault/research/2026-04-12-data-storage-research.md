---
name: data-storage-research
description: Survey of persistence backends for aeat — modelo schemas, metadata, filing history, audit trails.
tags:
  - "#research"
  - "#data-storage"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-data-storage-adr]]"
  - "[[2026-04-12-base-module-structure-adr]]"
---

# data-storage research

## context

Issue wgergely/aeat#10. The project currently has no persistence. Before #6 (modelo
catalogue), #7 (portals), #9 (schema extraction), #11 (sync/diff), #14 (filing history),
and #17 (corpus) can produce durable artefacts, a single decision must be made: where
does structured state live and how is it evolved safely? The brief explicitly asks for
automated, reviewable migrations and honestly evaluates Google Sheets/Drive.

## constraints (from issue and CLAUDE.md)

- Single-user autónomo scenario now; possibly multi-user / web later.
- Schema **will** evolve continuously — migrations are table stakes.
- Must play with pydantic/dataclasses cleanly; no bare dicts.
- Certificate bytes stay out of the DB; only references.
- Zero-config is strongly preferred for the current phase.
- Python 3.13, uv-managed, src layout, tests via pytest exclusively.
- Public API discipline: callers import from `aeat.adapters.persistence.storage` only.
- Sibling branches:
  - `#14` owns filing fixtures / `src/aeat/domain/testing/` — storage tests use inline fixtures.
  - `#15` owns pytest config — do not touch.
  - `#16` / `#20` may amend `src/aeat/config.py`; additive only, no clobber.
  - `#20` owns trilingual primitives — translatable fields MUST be stubbed with TODO markers.

## candidates

### 1. SQLite + SQLAlchemy 2.x + Alembic  *(default to beat)*

- **Migration story**: Alembic is the mature, reviewable, reversible, auto-generating
  migration tool on top of SQLAlchemy metadata. Upgrade/downgrade round-trip is a
  first-class concept.
- **Query expressiveness**: full SQL; joins across filings × casillas × schemas × portals
  are natural. SQLAlchemy ORM + `select()` API are typed with 2.x-style mapped columns.
- **Type safety**: SQLAlchemy 2.x `MappedAsDataclass` / `Mapped[...]` integrates with type
  checkers; pydantic models sit on top for wire/config.
- **Operational footprint**: zero. A single file under `var/aeat.db`. No server, no
  container, no port. Backups are `cp`.
- **Backup / portability**: copy the file; or `sqlite3 .dump` → SQL text for diffs.
- **Cost**: $0, bundled with Python stdlib.
- **Fit with CLI-first / web later**: excellent for CLI. For multi-user web, switching to
  Postgres later is a *connection string change* plus a migration review — this is
  exactly the upside of standardising on SQLAlchemy+Alembic now.
- **Security for certificate metadata**: fine; store file paths + sha256, never bytes.
- **Gotchas**: writer concurrency (single writer at a time; WAL mode mitigates for
  readers). Not an issue for single-user.

### 2. PostgreSQL + SQLAlchemy + Alembic

- Same ORM/migration story — the *portable* upgrade path from SQLite.
- **Ops footprint**: heavy. Requires docker-compose / managed instance / at minimum a
  local `postgres` service. The brief explicitly prefers zero-config "for now".
- **Value-add over SQLite**: real concurrency, advanced types (JSONB, arrays, range),
  logical replication. None of these are needed today.
- **Verdict**: correct long-term target when multi-user lands; premature today.

### 3. DuckDB + SQLAlchemy

- Analytical/columnar, single-file, OLAP-leaning.
- Migration tooling is nascent (`duckdb-engine` for SQLAlchemy works; Alembic support is
  possible but less battle-tested than on SQLite).
- Shines on aggregate/reporting queries; the workload here is OLTP-shaped (read/write a
  filing, read back a modelo schema).
- **Verdict**: wrong workload shape; ecosystem less mature for migrations.

### 4. Google Sheets / Drive as primary backend  *(user explicitly raised)*

- **Pros**: familiar GUI, Workspace MCP already wired, user can eyeball state live.
- **Cons**:
  - **Schema enforcement**: zero. A user (or a bug) can rewrite any cell.
  - **Migrations**: there is no reviewable migration story. "Add a column" is a manual
    UI edit; "rename a column" is a human dance.
  - **Concurrency**: last-write-wins. Unacceptable for filing history where every write
    is legally meaningful.
  - **Audit**: Sheets revision history is not a legal audit log.
  - **Query expressiveness**: no joins; `VLOOKUP` is not a join.
  - **Type safety**: strings and floats; pydantic integration is lossy on read-back.
  - **Cost / scale**: quota limits at the API layer.
  - **Security**: certificate references and personal tax IDs in a shared Google doc is a
    compliance smell.
- **Verdict**: unsuitable as the primary store. **Correct role**: an *export target* for
  human inspection of selected read-only views (already supported by the Workspace MCP
  tooling). This can be revisited in a future issue; no primitives are needed now.

### 5. TinyDB / JSON files under git

- Diff-friendly, version-controlled, no ops.
- **Migrations**: hand-rolled; no reviewable tool.
- **Concurrency**: file-level; merge conflicts on every filing.
- **Queries**: none — object scans only.
- **Verdict**: acceptable only for genuinely static catalogues. Filing history is not
  static.

### 6. Hybrid: relational primary + Sheets export

- Reduces to option 1 or 2 plus an export adapter.
- Adds no complexity *now*; the export adapter is a later issue.
- **Verdict**: this is the end state. Implement the relational primary now. Leave the
  export target to a follow-up.

## decision inputs for the ADR

1. All listed candidates share one objective winner for the *current* phase: **SQLite +
   SQLAlchemy 2.x + Alembic**. It satisfies zero-ops, migrations, query expressiveness,
   type safety, and a clean Postgres upgrade path behind a single connection string.
2. The brief's own "Notes" section nudges toward SQLAlchemy + Alembic explicitly.
3. Translatable fields (modelo names, casilla labels, portal labels) MUST be stubbed
   with a `TODO #20` marker — `#20` owns the trilingual primitive and we do not compete.
4. First-cut tables are **exactly** those consumed by near-term issues: `modelos`,
   `portals`, `corpus_artifacts`. Nothing else. Filing history (#14) and schema
   versioning (#9) will add tables in their own migrations.

## open questions (deferred)

- Export-to-Sheets adapter: separate issue, not blocking.
- Full-text search on casilla labels: not needed until #9 is wired.
- Multi-tenant row-level security: not needed until multi-user.

## conclusion

Commit to **SQLite + SQLAlchemy 2.x + Alembic** as the primary backend, behind a
configurable connection string so later swapping to PostgreSQL is a one-line change.
