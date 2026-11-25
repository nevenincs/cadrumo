---
tags:
  - '#reference'
  - '#cold-start-performance'
date: '2026-11-05'
modified: '2026-11-05'
body_schema: 'body-v2'
body_hash: 'sha256:71226cb3125d5d180f5e2bf7e40eaf789fbc37a4673d012e5a1ef4a82092cb0e'
related: []
---

# `cold-start-performance` reference: `Process state left at aeat command return`

What a one-shot `aeat` process still holds when its command returns, and which of it finalization would change. Sources: the cold-start profiling run of 2026-11-05 (teardown measured as soft exit against `os._exit`, 10 interleaved rounds), a probe that ran `bootstrap.main` and listed threads, exit hooks and open resources before and after `atexit._run_exitfuncs()`, and the code locators below.

## Summary

- Teardown cost: about 184 ms after a first registry snapshot (115k GC objects, 658 modules) and about 97 ms after a plain registry import. Sampling profilers do not see it.
- Console entry: `pyproject.toml` `[project.scripts]` names `cadrumo_runtime.host.frontend.cli.bootstrap`; the native host resolves the same console entry point through `native/interpreter/bootstrap.py:179-190` and, after Python returns, only frees memory (`native/interpreter/windows/host.c:164-170`, `native/platform/src/lib.rs:404-410`).
- In-process callers of `bootstrap.main` continue after it returns: `src/cadrumo_runtime/host/tests/frontend/cli/fresh_process.py:15-36`, `src/cadrumo/tests/subprocess_cli.py:110-137`, `dev/readme/prepare_cli_demo.py:32`.
- Product exit hooks: session sealing `src/cadrumo/adapters/persistence/storage/master_key/active_session.py:338`, logging shutdown `src/cadrumo/core/logging.py:1010`, lockfile release `src/cadrumo/adapters/persistence/storage/bucket/lockfile.py:548`, KDF worker close `src/cadrumo/adapters/persistence/storage/custody/kdf_supervision.py:600`, bundled resource stack `src/cadrumo/core/resources/bundled_data.py:62`. `weakref.finalize` users (`native_wake.py:78`, `change_witness.py:140`) run through the same hook registry. No production class defines `__del__`.
- Probe, `--help` and `--version`: only the main thread, four exit hooks, and the standard streams open.
- Probe, `app modelo describe 130` and `config profile list`: two daemon logging threads; the log file is open until the hooks run and closed after them; `describe` keeps four SQLite connections open after the hooks, opened read-only with `query_only` by `src/cadrumo/domain/calculations/registry/authority_store.py:481-489`, none in a transaction.
- Engines created by `get_engine` stay cached in `src/cadrumo/adapters/persistence/storage/sql/engine.py:289-319` unless the bucket session disposes them; closing the last connection checkpoints the write-ahead log (`engine.py:79-91`).
- `aeat app tui` starts the TUI as a separate child and waits for it (`src/cadrumo_runtime/host/frontend/cli/tui_launcher.py:26-35`).
- A scan of `gc.get_objects()` by concrete type costs about 12 ms per 47k objects on this machine; `isinstance` against the `io.IOBase` ABC costs about 30 ms for the same set.
