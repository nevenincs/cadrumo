---
tags:
  - '#adr'
  - '#cold-start-performance'
date: '2026-11-05'
modified: '2026-11-06'
body_schema: 'body-v2'
body_hash: 'sha256:b082fa78557c36e37d84f6f3939458fa2a5e2c2eb57e728e483e4232f6c138b6'
related:
  - "[[2026-07-02-arch-remediation-engine-lifecycle-adr]]"
  - "[[2026-08-22-secure-storage-performance-hardening-adr]]"
  - '[[2026-11-06-cold-start-performance-secure-storage-core-reference]]'
---

# `cold-start-performance` adr: `Secure-object storage on SQLAlchemy Core` | (**status:** `accepted`)

Accepted 2026-11-05: the operator authorized implementing the cold-start profiling findings on 2026-11-05.

## Problem Statement

Importing the secure-object repository costs about 600 ms on a cold Windows process, and every profile-bound command pays it. The SQL storage layer declared its two tables as ORM mapped classes and ran every statement through an ORM `Session`, so loading it also loaded `sqlalchemy.orm` (about 57 ms, 38 modules) although nothing in the layer maps rows onto objects.

## Considerations

- The repository never instantiated a mapped row and never used add, merge, flush or identity-map behaviour; it used the session only as a connection holder, the mapped class only as a column namespace, and `create_all` on its metadata (`src/cadrumo/adapters/persistence/storage/sql/secure_objects.py`, `src/cadrumo/adapters/persistence/storage/sql/_secure_object_writes.py`).
- The ledger date index used one ORM insert (`add_all`) inside the sibling-table write transaction (`src/cadrumo/adapters/persistence/profile/transaction_date_index_storage.py`).
- The persisted schema, the write funnel, AEAD row binding and the SERIALIZABLE plus `BEGIN IMMEDIATE` writer reservation are persistence guarantees that must not change (`2026-08-22-secure-storage-performance-hardening-adr`, `2026-07-02-arch-remediation-engine-lifecycle-adr`).

## Considered options

- Keep the ORM: no migration risk, but the import cost stays on every cold start for no behaviour the layer uses.
- Move to SQLAlchemy Core tables and connections: removes the ORM from the storage import graph while keeping SQLAlchemy's dialect, pooling, type decorators and engine lifecycle. Chosen.
- Replace SQLAlchemy with the `sqlite3` module: saves more (about 230-270 ms), but rewrites engine lifecycle, pooling, type processing and the `HashedLookup` column contract; a separate and larger decision.

## Constraints

- The DDL the engine and the repository materialise stays byte-identical; a database created before and after the change has the same `sqlite_master`.
- `session_scope` keeps its contract: one connection, one transaction, commit on success, rollback and debug log on exception; with `serializable=True` it sets SERIALIZABLE isolation and on SQLite issues `BEGIN IMMEDIATE` before the body reads anything.
- The write funnel, revision-guarded batches, CAS deletions, AAD binding, WAL pragmas and engine lifecycle are unchanged.
- Repository code does not import `sqlalchemy.orm`.

## Implementation

We will declare the storage schema as Core `Table` objects on one `MetaData` in `src/cadrumo/adapters/persistence/storage/sql/tables.py`, have `session_scope` yield a Core `Connection` inside its transaction, and express every statement against the table columns. Whole-row reads select the table and consume `Row` objects; the date index inserts with one Core executemany. The ORM mapping module is removed together with every consumer, including tests, which now tamper rows with explicit `UPDATE` statements.

## Rationale

Core supplies everything the layer actually uses, so the change removes import cost without changing behaviour. The DDL comparison and the existing transaction and lineage tests are the acceptance evidence that the persistence guarantees are unchanged.

## Consequences

- Loading the secure-object repository or the transaction catalogue no longer loads `sqlalchemy.orm`; the saving holds wherever no other module imports the ORM.
- Future storage code expresses reads and writes as Core statements; introducing ORM mapping would need a new decision.
- SQLAlchemy itself remains the largest import in this path; replacing it would be the separate `sqlite3` option above.
