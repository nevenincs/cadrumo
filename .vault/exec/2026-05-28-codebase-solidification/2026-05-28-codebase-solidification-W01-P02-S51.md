---
step_id: S51
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P02.S51 — hoist _overview.py logger to module level

## Outcome

Added `from ...core.logging import get_logger` import to
`src/aeat/entrypoints/cli/_overview.py`. Added `logger = get_logger(__name__)`
at module level (after the `app = typer.Typer(...)` block). Removed the
function-body `import logging` and `_log = logging.getLogger(__name__)` from
the `overview_calendar` command and replaced `_log.warning(...)` with
`logger.warning(...)`.

## Files touched

- `src/aeat/entrypoints/cli/_overview.py`

## Verification

`uv run --no-sync python -c "import aeat.entrypoints.cli._overview; print('OK')"` — OK.
`uv run --no-sync pytest src/aeat/entrypoints/cli/test_overview.py -xvs` — 3 passed.
`vault plan step check S51` applied.
