---
tags:
  - '#audit'
  - '#test-suite-budget'
date: '2026-10-31'
modified: '2026-10-31'
body_schema: 'body-v2'
body_hash: 'sha256:28127e2aea33be16c71b90e6da977d8d6db870c4b1fbe98449a57e0bb18a1d4c'
related:
  - "[[2026-10-30-test-suite-budget-plan]]"
---



# `test-suite-budget` audit: `cli-file-operations`

## Scope

Why one CLI command shows 6,000 to 18,000 non-read, non-write I/O operations. Measured with an in-process ntdll hook across client, runtime, worker and KDF child, reconciled against `psutil` `other_count`, with py-spy for wait time. ETW was refused without elevation, so there is no kernel view. All runs were on a loaded shared box. Savings are estimates; no fix was built.

## Findings

### operation-count | medium | The count is real, larger than first reported, and mostly metadata calls

A repeat calculate shows about 41,700 `other`: client 29,332, worker 8,128, runtime 2,162, KDF child 1,947. The model explains all but about 3%. `other_count` counts open, stat and close metadata calls, not reads.

### repeated-reads | low | The client is not re-reading files

92% of client operations are imports, and 1,669 `.pyc` opens hit 1,668 distinct files. The breadth is the defect: `aeat --help` loads 525 to 580 modules.

### syscall-cost | medium | File syscalls are about 10% of command wall time

Excluding fsync and KDF wait, syscalls take 0.5 to 0.9s in the client, about 0.2s in the worker and about 50ms in the runtime, against 7.5 to 11s of wall time. The removable share is estimated at 50 to 150ms per command. py-spy of the client shows wait 47.7%, IPC wait 20.3%, import execution 13.5%, import stat and read 3.1%.

### journal-revalidation | medium | Journal root validation runs on every read

`src/cadrumo/application/journal_repository.py:285` and `:288` resolve paths 2,072 times per calculate through `_validate_existing_root`, whose docstring says it is a location check and not protection against concurrent replacement. In the in-process fixture the journal class reached 17,315 of 30,991 operations. Resolving once per repository instance while keeping the per-read lexists and non-link checks is estimated to save 20 to 150ms. It weakens a recheck, so it needs a security judgement.

### journal-fsync | high | Journal durability is the largest file cost seen in tests

In the fixture calculate, the journal class took about 7.4s of 32.3s, with `sql/session.py:68` at 7,083ms. An earlier run had 79 flushes costing 3,751ms. `atomic_write.py:443` fsync took 301ms on the real path. fsync measured 1.8ms in one window and 152ms in a loaded one, so load dominates. The flush split for the exact window was not retained, and the suite share is not established.

### root-validation | low | One storage root is validated about ten times per process

`src/cadrumo/core/storage_environment.py:245` walks every parent with lstat: 340 operations, about 10ms. A fix needs a security judgement.

### justified | info | Operations with a stated invariant

Keep `atomic_write.py:443` fsync (durability), `filesystem_primitives.py:356` and `:369` (TOCTOU), `profile_worker_binding.py:71` (replacement detection) and `log_file_handler.py:391` (multiple writers).

### agent-correction | info | `installed_product_version` is already cached

`src/cadrumo_client/transport/product_version.py` already uses `functools.cache`, so its 401 operations are once per process; a further cache would save nothing. Deferring asyncio in `src/cadrumo_runtime/host/frontend/cli/tui_launcher.py:11` helps only commands that never connect, because connecting commands load asyncio anyway.

### defender | info | No measurable effect on cached opens

Open and close took 19.8 microseconds before the `.tmp` exclusion and 22.6 after, under different load. This is not a clean comparison; S14 stays open.

## Recommendations

Decide whether journal writes per command can be reduced by design; this is the largest lead in the record. Decide separately whether journal root resolution may be held per repository instance.
