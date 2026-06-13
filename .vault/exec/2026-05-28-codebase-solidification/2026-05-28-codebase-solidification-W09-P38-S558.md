---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: 'S558'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-28-codebase-solidification-adr]]'
---

# `codebase-solidification` `W09.P38.S558`

Added `ANY-RETURN-RATIONALE-PROFILE-LAZY-MODULE` inline markers on the three lazy-module helpers in `core/profile.py`.

- Modified: `src/aeat/core/profile.py`

## Description

The block comment at line 127 already documented the circular-import motive. Each of the three helper definitions (`_m`, `_p`, `_ccaa`) now carries the marker token inline on the `def` line, satisfying the per-def marker requirement and making inventory tooling able to assert coverage without parsing the block comment.

## Tests

Covered by the S561 inventory test `test_profile_lazy_module_helpers_carry_any_return_rationale`. Commit: `1c2b02e82`.
