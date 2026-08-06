---
step_id: S203
date: 2026-05-28
modified: '2026-07-17'
body_hash: 'sha256:20753f3a842a38e5ddc639b24ad2d02895430716a8fb24021fb445c1db65bd54'
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
