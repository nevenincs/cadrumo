---
step_id: S45
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
  - '[[2026-05-31-core-authority-action-tracker-v2-reference]]'
---

# core-authority W05.P15.S45 — remove _VerifyVerdict private duplicate (RENAME-005)

## Files modified

- `src/aeat/entrypoints/cli/_app_live.py` — removed `_VerifyVerdict = Literal[...]` declaration; moved `VerifyVerdict` import from `application/live/_verify` into the existing `TYPE_CHECKING` block; removed `Literal` from the `typing` import (no other uses)

## Commit

`95499fc55` — refactor(cli): remove _VerifyVerdict private duplicate, import from application layer (RENAME-005 W05.P15.S45)

## Before / After

- Before: `_VerifyVerdict = Literal["valid", "invalid", "unknown"]` declared at module level; function typed `-> _VerifyVerdict | None`
- After: `VerifyVerdict` imported under `TYPE_CHECKING` from `application.live._verify`; function typed `-> VerifyVerdict | None`

`from __future__ import annotations` makes the annotation a string at runtime, so the `TYPE_CHECKING`-only import is sufficient.

## Test run

```
pytest src/aeat/entrypoints/cli/test_live_read_subgroups.py -q
# → 21 passed
```
