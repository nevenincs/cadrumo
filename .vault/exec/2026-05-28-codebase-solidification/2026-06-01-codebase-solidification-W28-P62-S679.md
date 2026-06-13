---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-06-01'
modified: '2026-06-01'
step_id: 'S679'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W28.P62.S679`

Added `BROAD-EXCEPT-RATIONALE-SUBPROCESS-GUARD` marker comment immediately preceding all 3 `raise RuntimeError(` sites in `_doc_reference.py`.

- Modified: `src/aeat/entrypoints/cli/_doc_reference.py`

## Description

Three subprocess-guard `RuntimeError` sites exist in `_doc_reference.py`:
- Line 130 (import-failure fallback detection)
- Line 719 (CLI reference generation subprocess failure)
- Line 781 (CLI leaf-path collection subprocess failure)

Each site received the inline marker on the line immediately preceding the `raise`:

```
# BROAD-EXCEPT-RATIONALE-SUBPROCESS-GUARD: subprocess invocation failure surfaced as RuntimeError for operator diagnostics; not on the operator-facing AeatError contract.
```

The marker token is within 1 line preceding each raise, satisfying the "within 3 lines" postcondition.

## Tests

Verified by `test_s679_subprocess_guard_markers_precede_all_runtime_errors` in `test_w28_p62_closure.py`. All 8 tests (1 S679 check + 7 ratchets) passed in 14.10s.
