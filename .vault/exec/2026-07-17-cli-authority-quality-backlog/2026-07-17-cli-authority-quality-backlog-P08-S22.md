---
tags:
  - '#exec'
  - '#cli-authority-quality-backlog'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:1a8a8c3cf2f7f56fd4c1329f4cc7cc0d643d10c32d1eb1a7c0f1d58a9bf20696'
step_id: 'S22'
related:
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
---

# Give the acceptance-wall meta-test a per-worker unique temp root via tmp_path_factory so concurrent pytest workers no longer share a PID-keyed directory and race

## Scope

- `src/cadrumo/tests/test_acceptance_wall_catalogue.py`

## Description

- Reproduce the flake first: run the meta-test module under two concurrent `-n auto` invocations (the "parallel agents sharing this worktree" scenario). Both runs failed deterministically on `test_a_regressed_wall_assertion_is_caught_by_the_gate` with a subprocess collection abort: `FileNotFoundError: ...\Temp\acceptance-wall-junit-<suffix>` — the `_batched_wall_results` fixture's `tempfile.TemporaryDirectory` in the bare shared OS temp root, deleted at its `with`-block exit mid-session while a concurrent worker still resolved paths under the shared temp.
- Replace the module-scoped fixture's `tempfile.TemporaryDirectory(prefix="acceptance-wall-junit-")` with `tmp_path_factory.mktemp("acceptance-wall-junit")`: a pytest-managed, per-worker-namespaced, session-lived directory that no concurrent run deletes out from under a sibling.
- Remove the now-unused `import tempfile`.
- Drop the redundant `os.getpid()` key from the anti-tautology test's mutated-module filename; `tmp_path` is already per-worker unique and session-lived, so no PID key is needed to avoid a cross-worker basename collision.

## Outcome

The reproduced concurrency failure is closed. After the fix, two more concurrent `-n auto` pairs both went fully green (32 passed each), where the pre-fix pair failed deterministically (1 failed, 31 passed on both). Single-run behaviour is unchanged (32 passed). Ruff clean; collection clean. Every temp path the meta-test owns is now a pytest-managed per-worker root, not a bare shared-OS-temp directory or a PID-keyed name.

## Notes

Root cause was the shared-OS-temp `TemporaryDirectory` lifecycle, not the storage-root derivation (`collection_storage_root()` is genuinely process-private by PID and lives in `_collection_storage_root.py`, out of this step's scope and not the fault). No mocks, skips, or xfail were introduced — the fix is real-behaviour and empirically proven by re-running the exact concurrent scenario that failed before it.
