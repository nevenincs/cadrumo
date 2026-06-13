---
step_id: S492
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-31
modified: '2026-05-31'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W06.P29.S492

**Step**: extract _SYSTEMROOT_ENV_VAR and _USERDOMAIN_ENV_VAR Final constants in core/file_permissions.py.

## Outcome

Added `_SYSTEMROOT_ENV_VAR: Final[str] = "SYSTEMROOT"` and `_USERDOMAIN_ENV_VAR: Final[str] = "USERDOMAIN"` as module-level constants with `typing.Final` import. Both `os.environ.get()` call sites migrated to use the constants.

## Files

- `src/aeat/core/file_permissions.py`

## Commit

5b45dd58c
