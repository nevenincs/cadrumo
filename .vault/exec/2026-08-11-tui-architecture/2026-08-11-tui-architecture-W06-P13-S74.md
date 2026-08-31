---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:ebd7365cc983e8e1da903e987e894940a2d95fc2a04dd7bab764cd42b4840d91'
step_id: 'S74'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Delegate module execution directly to the TUI launcher without importing the CLI

## Scope

- `src/cadrumo/entrypoints/tui/__main__.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/__main__.py`
- `A` `src/cadrumo/entrypoints/tui/tests/test_module_execution.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/tests/test_module_execution.py -m integration -n0` -> `pass`
- `verify:` `uv run --no-sync pytest dev/tests/test_importlinter_tui_boundaries.py -m integration -n0` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.types` -> `pass`

## Notes

The module is executed as its own process in the proofs rather than
imported. A delegation that resolves its symbol and then fails to start is
invisible to an import-based assertion, and that failure mode was real here
twice already: the launcher entry point first could not compose, then
started and never terminated.

Assertions read the terminal control sequence a Textual session emits and
the process's own behaviour, never rendered prose. The prose is locale data
the app reads from the catalogue a test would read it from, so asserting it
would prove only that one file was consulted twice.

Both proofs were shown to bite by replacing the launcher entry point in the
child process from outside the repository: a hollow entry point that returns
success without starting reds the session proof, and one that raises reds
both. Nothing under `src/` was edited to obtain either result.

Files were carried to main inside `a4198bed42`, a separate same-day commit
by another author, before this Step could commit them; content verified
identical at HEAD. The type-narrowing correction landed as `863556d806`.
