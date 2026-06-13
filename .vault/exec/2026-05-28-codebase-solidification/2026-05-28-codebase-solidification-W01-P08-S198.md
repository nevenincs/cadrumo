---
step_id: S198
date: 2026-05-28
modified: '2026-05-28'
tags:
  - "#exec"
  - "#codebase-solidification"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W01.P08.S198

Created `src/aeat/adapters/outbound/google/test_api.py` with real-behavior tests:

- Protocol structural check via live `execute_request` call.
- Response shape asserted as `dict` / `GoogleApiResponseBody`.
- HTTP 401/403 → `OutboundStoragePermissionError`, 404 → `OutboundStorageNotFoundError`, 500/generic → `OutboundStorageNetworkError`.
- `OutboundStorageError` re-raise contract (no re-wrapping).
- Added `test_api.py` to module allowlist.

All 9 tests pass. Commit: `491d6af66`
