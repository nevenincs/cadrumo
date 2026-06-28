---
step_id: S197
date: 2026-05-28
modified: '2026-05-28'
tags:
  - "#exec"
  - "#codebase-solidification"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W01.P08.S197

Narrowed `execute_request` in `src/aeat/adapters/outbound/google/_api.py`:

- Added `_ExecutableRequest` Protocol covering `execute(http, num_retries) -> Any`.
- Added `GoogleApiResponseBody = dict[str, Any]` type alias.
- Changed `request: Any` → `request: _ExecutableRequest`.
- Changed return `-> Any` → `-> GoogleApiResponseBody`.
- Annotated the internal `result` variable to confirm the narrowing.

Collision check: clean diff on target file before edit.
Commit: `491d6af66`
