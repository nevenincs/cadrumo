---
tags:
  - '#reference'
  - '#cold-start-performance'
date: '2026-11-06'
modified: '2026-11-06'
body_schema: 'body-v2'
body_hash: 'sha256:e133b37d9a2bff0ae4d00250b56b565809192e21fd929041a5843f509eabd2b9'
related: []
---

# `cold-start-performance` reference: `secure storage core`

Evidence for the move of the secure-object storage layer from ORM mapped classes to SQLAlchemy Core tables. Sources: the tree at commit `ec5e409956^` (before) and at `ec5e409956` (the Core change, which is also the base of the measured current tree), and `-X importtime` measurements taken for this record.

## Summary

The layer imported `sqlalchemy.orm` only to declare two tables and to hold a connection. Nothing in it used ORM object behaviour. After the change the secure-object repository no longer loads `sqlalchemy.orm` at all.

## Code facts before the change (`ec5e409956^`)

- Two tables were declared as mapped classes on a `DeclarativeBase`: `src/cadrumo/adapters/persistence/storage/sql/orm.py:24` imports `DeclarativeBase, Mapped, mapped_column`; `:38` `class Base(DeclarativeBase)`; `:72` `TransactionDateIndexRow`; `:141` `SecureObjectRow`; `:192` `metadata = Base.metadata`.
- The unit of work was an ORM session factory: `src/cadrumo/adapters/persistence/storage/sql/session.py:16` imports `Session, sessionmaker`; `:34` builds `sessionmaker(bind=..., expire_on_commit=False)`; `:57-67` opens a session, reaches its connection for SERIALIZABLE and `BEGIN IMMEDIATE`, then yields the session.
- The repository imported the ORM at module load: `src/cadrumo/adapters/persistence/storage/sql/secure_objects.py:12` (`Session`) and `:31` (`SecureObjectRow`). It used the mapped class as a column namespace in `select(SecureObjectRow.col)` (`:372`, `:401`, `:430`) and `inspect(SecureObjectRow).local_table` (`:125`).
- No ORM object behaviour in the storage layer: a search of `secure_objects.py` and `_secure_object_writes.py` at that commit finds no `session.add`, `merge`, `flush`, `refresh`, `expunge`, `get` or `add_all`.
- The one ORM write was the date index: `src/cadrumo/adapters/persistence/profile/transaction_date_index_storage.py:15` imports `TransactionDateIndexRow` and `:102` calls `session.add_all(new_rows)`.

## Code facts after the change (`ec5e409956`)

- Core tables replace the mapped classes: `src/cadrumo/adapters/persistence/storage/sql/tables.py:39` `metadata = MetaData()`, `:42` `transaction_date_index_table = Table(...)`, `:107` `secure_objects_table = Table(...)`. `orm.py` is deleted.
- `src/cadrumo/adapters/persistence/storage/sql/session.py:14` imports `Connection, Engine` only; `:23` `session_scope` yields a `Connection`; `:46` sets `isolation_level="SERIALIZABLE"` and `:52` still issues `BEGIN IMMEDIATE`.
- The date index inserts with one Core executemany: `src/cadrumo/adapters/persistence/profile/transaction_date_index_storage.py:102` `session.execute(insert(transaction_date_index_table), new_rows)`.
- A search for `sqlalchemy.orm` over `src` at the current HEAD finds no file importing it.

## Import-time measurements

Machine: Windows 11 Pro 10.0.26300, CPython 3.13.15 from the repository virtual environment, SQLAlchemy as installed there. Each round is a fresh process: `python -X importtime -c "import cadrumo.adapters.persistence.storage.sql.secure_objects, sys; ..."` with `PYTHONPATH` pointing at the tree under test (the editable install otherwise resolves to a different checkout) and the tree as working directory. Cumulative microseconds as printed by `-X importtime`, five rounds each, median reported. The before tree is a detached worktree at `ec5e409956^`; the after tree is the current HEAD. Figures vary strongly between rounds (the first round of each series is the slowest) and rounds were not isolated from other load on the machine, so they bound the effect rather than fix it.

| Quantity | Before (`ec5e409956^`) | After (current HEAD) |
|---|---|---|
| `sqlalchemy.orm` in `sys.modules` after import | True, 38 modules | False, 0 modules |
| Repository module cumulative, median | 769732 us (rounds: 1183065, 719161, 769732, 785752, 607406) | 643816 us (rounds: 714946, 646643, 568915, 643816, 624577) |
| `sqlalchemy` cumulative, median | 366041 us | 372116 us |
| `sqlalchemy.orm` cumulative, median | 65797 us (rounds: 94045, 69380, 65797, 63791, 56517) | not imported |

Reading: the 38-module ORM import and its cost (56517 to 94045 us per round, median 65797 us) are measured and removed. The repository module total on this machine was about 0.6 to 0.8 s per cold process in both trees; the difference between the two medians (about 126 ms) is larger than the ORM import alone and is within the round-to-round noise, so it is not claimed as the saving. The ORM import is the attributable part.

## Not established here

- The ADR's own figures (about 600 ms, about 57 ms, 38 modules) were not copied; the 38-module count and the ORM cost range above were measured independently, on a different machine state, so they differ in detail.
- Byte-identical DDL, SERIALIZABLE and `BEGIN IMMEDIATE` behaviour and the unchanged write funnel are claimed by the implementing commit and its tests; this record did not re-run those tests.
