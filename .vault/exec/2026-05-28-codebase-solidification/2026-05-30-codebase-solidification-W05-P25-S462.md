---
step_id: S462
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W05.P25.S462

## Step

Introduce `PROVENANCE_SOURCE_MANUAL_CLI: Final[str] = "manual_cli"` in `external_constants` and migrate `user_profile/__init__.py:92,103`, `_values.py:134`, `_testing.py:45`.

## Outcome

- Added `PROVENANCE_SOURCE_MANUAL_CLI: Final[str] = "manual_cli"` to `external_constants.py`.
- `application/user_profile/__init__.py`: imported as `_PROVENANCE_SOURCE_MANUAL_CLI`; replaced 2 `Field(default="manual_cli", ...)` occurrences.
- `domain/user_profile/_values.py`: imported as `_PROVENANCE_SOURCE_MANUAL_CLI`; replaced `source: _Source = "manual_cli"`.
- `application/user_profile/_testing.py`: imported as `_PROVENANCE_SOURCE_MANUAL_CLI`; replaced `"provenance.source": "manual_cli"`.
- 28 domain user_profile tests pass.

## Files touched

- `src/aeat/core/external_constants.py`
- `src/aeat/application/user_profile/__init__.py`
- `src/aeat/domain/user_profile/_values.py`
- `src/aeat/application/user_profile/_testing.py`
