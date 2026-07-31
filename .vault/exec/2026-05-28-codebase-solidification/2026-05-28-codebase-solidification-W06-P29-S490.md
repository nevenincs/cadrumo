---
step_id: S490
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-31
modified: '2026-07-17'
body_hash: 'sha256:6f7d2bcb09b7b13f99dca94f01380d62b7cfe8ac92f373638602e9bbdc7280a9'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W06.P29.S490

**Step**: delete SEDE_BODY_ENCODING duplicate in sede/_browser_constants.py and import LATIN_1_ENCODING from external_constants instead.

## Outcome

`_browser_constants.py` now imports `LATIN_1_ENCODING` from `external_constants` and defines `SEDE_BODY_ENCODING: Final[str] = LATIN_1_ENCODING` — eliminating the duplicate `"latin-1"` definition while preserving the exported name for callers in `_declarations.py`.

## Files

- `src/aeat/adapters/outbound/aeat/sede/_browser_constants.py`

## Commit

5b45dd58c
