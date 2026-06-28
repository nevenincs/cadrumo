---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-06-01'
modified: '2026-06-01'
step_id: 'S677'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W27.P61.S677`

Added `LOGGING-STDLIB-RATIONALE-STDIO-PLATFORM-FALLBACK` marker on the line immediately preceding `import logging` in `_stdio.py`.

- Modified: `src/aeat/entrypoints/cli/_stdio.py`

## Description

W26 added `import logging` at line 27 without a rationale marker. Inserted the marker on line 27 (pushing `import logging` to line 28), explaining that stdlib logging is used for a debug-level platform diagnostic on Windows ctypes failure where core logging is unavailable at stream-bootstrap time.

## Tests

`test_w27_p61_closure.py::test_s677_logging_rationale_marker_precedes_import` — passed. Token found 1 line above `import logging`.
