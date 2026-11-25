---
tags:
  - '#adr'
  - '#cold-start-performance'
date: '2026-11-05'
modified: '2026-11-05'
body_schema: 'body-v2'
body_hash: 'sha256:ff34e219b3f3339637cbc8ae7262ec4184e96570351166657023eb1170718024'
related:
  - '[[2026-11-05-cold-start-performance-cli-exit-state-reference]]'
---

# `cold-start-performance` adr: `Settled fast exit for the one-shot aeat console process` | (**status:** `accepted`)

Accepted 2026-11-05. Basis: the operator authorized implementing the cold-start profiling findings on 2026-11-05; this records the first ranked candidate of that profiling.

## Problem Statement

A one-shot `aeat` invocation has already written its result when its command returns, yet full interpreter finalization then deallocates every imported module and object. The cold-start profiling measured that teardown at about 184 ms after a first registry snapshot (115k GC objects, 658 modules) and about 97 ms after a plain registry import, as soft exit against `os._exit` over interleaved rounds. That is pure latency for every CLI call; the measurements and the exit-time process state are recorded in `2026-11-05-cold-start-performance-cli-exit-state-reference`. Ending a process early is a process-lifecycle contract: it decides which cleanups are guaranteed and which hosts may skip finalization, so it needs a recorded decision.

## Considerations

- The console script target `cadrumo_runtime.host.frontend.cli.bootstrap` is the only owner of the `aeat` process; `bootstrap.main` is also called in-process by test harnesses and the README demo, which keep working after it returns.
- Product cleanups are registered as exit hooks or `weakref.finalize` callbacks (`active_session.py:338`, `logging.py:1010`, `lockfile.py:548`, `kdf_supervision.py:600`, `bundled_data.py:62`, `native_wake.py:78`, `change_witness.py:140`); no product class defines `__del__`.
- What the operating system cannot reproduce at process end is a userspace write buffer flush, a writable SQLite close (the last close checkpoints the write-ahead log), waiting for a foreground thread and a still-running child.
- The registry authority keeps four `mode=ro`, `query_only` SQLite connections open for the process lifetime (`authority_store.py:481-489`); they have nothing to commit or checkpoint.
- The native interpreter host runs the same console entry point through `run_entrypoint` and only frees memory after Python returns (`native/interpreter/windows/host.c:164-170`, `native/platform/src/lib.rs:404`).
- The runtime, MCP service, agent service and TUI are separate executables or a separate child (`tui_launcher.py`), with their own entry points.

## Considered options

- Keep the interpreter's exit: no risk, keeps the measured latency. Rejected as the profiling's top-ranked saving.
- `os._exit` unconditionally after the command: fastest, but drops buffered writes, writable SQLite checkpoints and foreground work. Rejected.
- An early-registered exit hook that calls `os._exit` last: uses only public API, but a hook registered before it (for example a coverage `.pth`) would be skipped. Rejected.
- Restrict by declared command policy (read-only verbs only): a policy says what a verb may do, not what the process still holds at exit. Rejected in favour of observing the process state directly.
- Chosen: a settled exit at the console entry that runs the exit hooks itself and ends the process only when it can show nothing would change by finalizing; otherwise the interpreter exits as before.

## Constraints

- Only the `aeat` console script (`bootstrap:console_main`) may end its process this way. `bootstrap.main`, in-process callers, CliRunner tests and every long-lived host keep the interpreter's exit.
- The status must equal what `SystemExit(code)` gives. A non-integer code, a code outside the C `int` range and any exception other than `SystemExit` are left to the interpreter.
- The fast exit happens only after the command's scopes have exited, no foreground thread is alive, every exit hook has run, the standard streams have flushed without error, and no open writable buffered stream, non-`query_only` SQLite connection or running child process remains. Any failed condition falls back to ordinary finalization.
- Development mode keeps the interpreter's exit so leaked-resource warnings stay visible.
- Operation settlement is unchanged: the CLI observes receipts before its command returns, and an ambiguous outcome is reported as `UNKNOWN` by the command, not by the exit.

## Implementation

We will make `cadrumo_runtime.host.frontend.cli.bootstrap:console_main` the `aeat` console script. It runs `main()`, captures the `SystemExit` code and calls `exit_settled_console_process` in `src/cadrumo_runtime/host/frontend/cli/console_exit.py`, which checks for foreground threads, runs `atexit._run_exitfuncs()`, flushes the standard streams, scans the GC-tracked objects of loaded modules for the unsettled resource types above, and calls `os._exit` with the integer status or raises `SystemExit(code)`. The Windows secret-handle bootstrap, which runs `main()` under `python -m`, keeps the interpreter's exit for now. The scanned type list is an implementation hypothesis that may grow within these constraints.

## Rationale

Observing the process state at the end is the only check that holds whatever a command did: it covers both reads and in-process writes without trusting declarations. Running the exit hooks explicitly preserves the existing cleanup order (threads, then hooks, then stream flush) that the interpreter itself uses, and the fallback keeps every unproven case byte-for-byte on the old path. The scan costs a few tens of milliseconds against a teardown of 100-185 ms.

## Consequences

- One-shot `aeat` calls end without interpreter teardown; a process holding a writable SQLite connection, an unflushed file, a foreground thread or a running child pays the old cost.
- The exit relies on the CPython-private `atexit._run_exitfuncs`, which is declared in typeshed and drains the hook registry. The operator ruled on 2026-11-05 to keep it, since the standard library offers no public way to run the hooks and a stdlib private cannot be made public. `src/cadrumo_runtime/host/tests/frontend/cli/test_atexit_drain_contract.py` guards the reliance in a fresh interpreter: the function and `atexit._ncallbacks` must exist and be callable, two drains must run a registered hook exactly once and leave no hook behind, and a hook registered after a drain must still run at the interpreter's own exit. A failure of that guard on a new CPython requires revisiting this decision before upgrading.
- A future cleanup that relies on object deallocation rather than an exit hook or `weakref.finalize` would be skipped; such cleanups must register an exit hook or extend the scan.
- `src/cadrumo_runtime/host/tests/frontend/cli/test_console_settled_exit.py` drives the real entry as a subprocess against the interpreter's exit for status, output, hooks and each fallback.
