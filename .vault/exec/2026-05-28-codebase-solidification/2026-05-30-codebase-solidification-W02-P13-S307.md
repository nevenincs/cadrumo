---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
step_id: 'S307'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W02.P13.S307`

Replaced `logging.getLogger` with `get_logger` from `aeat.core.logging` and eliminated two `print()` calls by folding their message into the adjacent `_log.debug(..., exc_info=True)` call.

- Modified: `src/aeat/adapters/outbound/aeat/sede/test_renta_web_open_explore_dom.py`

## Description

Removed the `import logging` statement and added `from .....core.logging import get_logger`. Changed `_log = logging.getLogger(__name__)` to `_log = get_logger(__name__)`. The two `print(f"explore: ... unreachable: ...")` calls at lines 175 and 208 (pre-edit) were merged into the preceding `_log.debug` call by appending the exception type and message as positional format args, keeping `exc_info=True`.

## Tests

File parses cleanly (`ast.parse` smoke check). No live tests affected — the file is `live_read`-gated and not run in the default suite.
