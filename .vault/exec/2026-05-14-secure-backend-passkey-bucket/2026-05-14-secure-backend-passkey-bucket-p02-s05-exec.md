---
tags:
  - '#exec'
  - '#secure-backend-passkey-safety'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'P02.S05'
related:
  - '[[2026-05-14-secure-backend-passkey-bucket-plan]]'
---

# secure-backend-passkey-safety P02.S05

Implement the per-bucket `.lock` concurrency primitive at
`src/aeat/adapters/persistence/storage/bucket/_lockfile.py` per ADR-2
section 11. `acquire_lock` uses an atomic `os.open` with
`O_CREAT | O_EXCL | O_WRONLY`; a second-process unlock attempt against a
held bucket fails fast with `BucketBusyError` carrying the holder's PID.

- Created: `src/aeat/adapters/persistence/storage/bucket/_lockfile.py`
- Created: `src/aeat/adapters/persistence/storage/bucket/test_lockfile.py`
- Modified: `src/aeat/adapters/persistence/storage/bucket/__init__.py`

## Description

`acquire_lock(paths, wait_seconds=0.0)` stamps the lockfile at
`<bucket-dir>/.lock` carrying the holder's PID. The exclusive-create
path is portable across POSIX kernels and Windows NTFS. When the
lockfile is already held the function probes the recorded PID for
liveness; if the PID is gone the stale lockfile is reclaimed and the
acquisition retries. When the holder is alive and the wait window
expires the call raises `BucketBusyError`.

`release_lock(paths)` deletes the lockfile only when the recorded PID
matches this process, so a stale-reclaim race cannot delete another
process's lock. An `atexit` hook releases every lockfile this process
still owns on normal interpreter shutdown; abnormal exits (SIGKILL, OS
crash, container OOM) bypass the hook and rely on lazy stale reclaim at
the next `acquire_lock`.

### Cross-platform liveness probe

POSIX uses `os.kill(pid, 0)` with `ProcessLookupError` distinguishing
dead from alive. Windows is harder: `os.kill(pid, 0)` reports
terminated-but-still-cached PIDs as alive. The Windows branch goes
through `kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` and
`GetExitCodeProcess`; a process whose exit code is anything other than
`STILL_ACTIVE` (259) is dead even if its PID is still allocated. A
foreign-user `OpenProcess` failure is treated as alive so we never
delete a lockfile we cannot prove dead.

## Open-question default honoured

Lockfile staleness detection: lazy reclaim at `acquire_lock` time using
the cross-platform PID-liveness probe described above (per the
orchestrator default). A `--force` override is deferred to a later
phase; the lazy reclaim covers every observed abnormal-exit shape.

## Tests

`test_lockfile.py` (7 tests; `pytest.mark.unit` +
`pytest.mark.domain_persistence`):

- Acquire-then-release round-trip; lockfile carries our PID.
- In-process re-entry is rejected (the typed payload carries our PID).
- Cross-process busy detection via a `subprocess.Popen` holder; the
  test reads the PID from the lockfile so it is robust against the
  Windows py-launcher PID-rebinding shape.
- `wait_seconds` window: a holder that releases within the wait window
  yields the lock to the waiting process.
- A stale lockfile carrying a known-dead PID (we spawn and reap a
  subprocess, then stamp its PID into the lockfile) is reclaimed.
- `release_lock` is idempotent when the lockfile is absent.
- `release_lock` leaves a foreign-PID lockfile alone.

`uv run pytest src/aeat/adapters/persistence/storage/bucket/test_lockfile.py -x -q` :
7 passed in ~11s.

Full P02 surface sweep
(`uv run pytest src/aeat/adapters/persistence/storage/bucket/
src/aeat/application/workflow/test_bucket_pointer_io.py -q`) : 67
passed.

`uv run ruff check` and `uv run ty check` clean on the new modules and
on the modified `__init__.py`.
