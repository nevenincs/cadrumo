---
tags:
  - "#exec"
  - "#codebase-solidification"
step_id: S177
date: '2026-05-28'
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-27-centralized-module-drift-audit]]"
---

# codebase-solidification W01.P07.S177 — centralise `BINARY_MIME_TYPE` constant

## Outcome

Added `BINARY_MIME_TYPE: Final[str] = "application/octet-stream"` to
`src/aeat/core/external_constants.py` (after tau2's `DEFAULT_CURRENCY`).
Migrated all three raw-literal sites.

## Files changed

- **Extended**: `src/aeat/core/external_constants.py` — appended `BINARY_MIME_TYPE`
- **Migrated**: `src/aeat/adapters/outbound/aeat/sede/_declarations.py` — raw literal at `content_type=` → `_BINARY_MIME_TYPE` import
- **Migrated + local deleted**: `src/aeat/adapters/outbound/storage/_google_drive.py` — removed `_BINARY_MIME = "application/octet-stream"`, imported `_BINARY_MIME_TYPE` from `external_constants`
- **Migrated**: `src/aeat/adapters/persistence/storage/blob_store/_blob_store.py` — default arg `"application/octet-stream"` → `BINARY_MIME_TYPE`

## Collision check

`git diff` on all five target paths before first edit returned empty. Tau2 had
uncommitted WIP adding `DEFAULT_CURRENCY` and `CSV_ENCODING_FALLBACK_CHAIN` to
`external_constants.py`. Detected on second read; insertion placed after
`DEFAULT_CURRENCY` without disturbing tau2 additions.

## Review gates (G1–G6)

All pass. No naked env reads, typed constant via `Final[str]`, no user-facing
strings, no locale edits, no shims (local `_BINARY_MIME` deleted from
`_google_drive.py`), no tautological tests.
