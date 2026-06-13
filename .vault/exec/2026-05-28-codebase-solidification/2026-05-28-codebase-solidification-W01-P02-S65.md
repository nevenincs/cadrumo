---
step_id: S65
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P02.S65 — auth waiting banner via structured logger

## Outcome

Replaced the `for line in lines: print(line, file=stream, flush=True)` loop
in `_render_progress_banner` at `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`
with a single `log.info("auth.waiting_banner banner=%r", banner)` call using the
module-level `log = get_logger(__name__)` instance.

Removed the now-unused `stream: IO[str] = sys.stderr` parameter from the function
signature. Removed unused `import sys` and `IO` from the imports since neither is
referenced elsewhere in the file.

## Files touched

- `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`

## Verification

77 tests pass. Commit: 2f51c3e0d. `vault plan step check S65` applied.
