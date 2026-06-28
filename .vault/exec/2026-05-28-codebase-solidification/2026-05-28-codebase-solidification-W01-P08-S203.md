---
step_id: S203
date: 2026-05-28
modified: '2026-05-28'
tags:
  - "#exec"
  - "#codebase-solidification"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W01.P08.S203

Added `@overload` signatures to `_scrub_value` in `src/aeat/core/logging.py`:

- `str → str`
- `Mapping[str, Any] → dict[str, Any]`
- `tuple[Any, ...] → tuple[Any, ...]`
- `list[Any] → list[Any]`
- `set[Any] → set[Any]`
- `object → object` (fallback)

The implementation body is unchanged; overloads provide static narrowing only. Added `overload` to `typing` import.

Commit: `491d6af66`
