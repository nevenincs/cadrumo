---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-07-17'
body_hash: 'sha256:2ac57b6a663284005bd7342c0f62534e2bba1345d6a153bac661b04697edca7f'
step_id: 'S560'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-28-codebase-solidification-adr]]'
---

# `codebase-solidification` `W09.P38.S560`

Replaced `from logging import Logger` with `import logging` and `logging.Logger` annotations in `sede/_browser_stage.py`.

- Modified: `src/aeat/adapters/outbound/aeat/sede/_browser_stage.py`

## Description

The file used `Logger` as a type annotation for the `logger` parameter in `build_playwright_stage_runner` and `run_playwright_stage`. Option (a) was chosen: `import logging` at the top-level plus `logging.Logger` at all annotation sites. This avoids the bare stdlib-name alias import while keeping the annotation local to the stdlib rather than requiring a `aeat.core.logging` re-export (which would be appropriate only if `get_logger` returns a subclassed type).

## Tests

Collected without import error. The sede test suite has pre-existing collection failures unrelated to this change (`aeat.adapters.core` module not found). Commit: `1c2b02e82`.
