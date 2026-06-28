---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: S580
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W10.P41.S580`

Added `ANY-RETURN-RATIONALE-SCRUB-OVERLOAD-IMPL` marker on the `_scrub_value` implementation overload in `core/logging.py`.

- Modified: `src/aeat/core/logging.py`

## Description

The `_scrub_value` implementation overload at line 147 returns `-> Any` to subsume all concrete overload return types per mypy overload rules. The marker documents this as an intentional overload-implementation pattern, not an untyped escape.

## Tests

W10 inventory test locates the implementation overload by searching for `def _scrub_value(` with `-> Any` and asserts the rationale token is present. 27/27 passed.
