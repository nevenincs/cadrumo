---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: 'S528'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W07.P33.S528`

REGRESSION FIX: deleted `src/aeat/core/_time.py` entirely. Module contained `utc_now()` which duplicated the canonical `_now()` in `aeat.core.time._clock`. Grep-post-condition confirmed zero callers before deletion.

- Deleted: `src/aeat/core/_time.py`

## Description

The module was dormant — `grep -rn "aeat.core._time" src/aeat/` returned no results. Deleted directly with no shim, no deprecation marker, per the retire-means-delete-fully rule.

Grep-post-condition output: empty (0 lines). The canonical time helper at `aeat.core.time._clock` remains untouched.

## Tests

`test_aeat_core_time_module_deleted` — asserts `ModuleNotFoundError` when attempting `importlib.import_module("aeat.core._time")`.

`test_no_source_imports_aeat_core_time` — walks all production source files and asserts none contain the string `"aeat.core._time"`.

Both tests in `src/aeat/test_w07_p33_cleanup.py` passed.
