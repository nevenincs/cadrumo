---
step_id: S239
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-07-17'
body_hash: 'sha256:80801f7534882ee88945cba31849da17241abdc218c236db6e34b578a4be4edc'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P10.S239

**Delete `_MANUAL_CLASSIFIED_BY` shadow in `domain/transactions/_service.py`.**

## Files touched

- `src/aeat/domain/transactions/_service.py` — removed `_MANUAL_CLASSIFIED_BY = "manual"` at line 24; added `from ...core.external_constants import CLASSIFIED_BY_MANUAL`; updated call-site at line 196 from `_MANUAL_CLASSIFIED_BY` to `CLASSIFIED_BY_MANUAL`.

## Outcome

Domain layer now imports the constant from `aeat.core.external_constants`, eliminating the upward-layer violation. 135 tests pass.
