---
step_id: S460
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-07-17'
body_hash: 'sha256:29cbfa2f58ce91e4796299cf1533e04d6dbe848fe4df149eb8a44aebea58a30c'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W05.P25.S460

## Step

Migrate bare `"GENERAL"` at `user_profile/_testing.py:44` to `IVARegime.GENERAL`.

## Outcome

- Added `from ...domain.deadlines._models import IVARegime` import.
- Changed `"iva.regime": "GENERAL"` to `"iva.regime": IVARegime.GENERAL` in `_REQUIRED_PLACEHOLDERS`.
- `IVARegime.GENERAL` is a StrEnum member with value `"GENERAL"`, so the runtime string is identical.

## Files touched

- `src/aeat/application/user_profile/_testing.py`
