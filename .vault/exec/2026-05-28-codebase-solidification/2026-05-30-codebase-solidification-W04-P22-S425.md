---
step_id: "W04.P22.S425"
date: 2026-05-30
modified: '2026-05-30'
agent: coder-delta8
commit: e7f96f6ec
tags:
  - "#exec"
  - "#codebase-solidification"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# W04.P22.S425 — Canonical _parse_date helper + 3 wrapper migrations

Added `_parse_date(raw, *, fmt, on_error)` to `aeat.core.parsing._dates` with
`fmt: Literal["iso8601","ddmmyyyy"]` and `on_error: Literal["raise","none"]`.
Overloads supplied for type-checker precision. Exported from `core.parsing.__init__`.

Three local wrappers migrated:
- `sede/_notifications.py`: renamed `_parse_date` to `_parse_date_local`; calls
  `_parse_date(raw, fmt="ddmmyyyy", on_error="none")` — silent-None policy.
- `sede/_censo.py`: imports canonical as `_parse_date_canonical`; local
  `_parse_date(raw, *, field)` calls canonical then wraps ValueError as CensoParseError.
- `domain/deadlines/_profiles.py`: imports canonical as `_parse_date_canonical`;
  local `_parse_date(raw)` calls canonical then wraps ValueError as ProfileError.

**Files touched:** `src/aeat/core/parsing/_dates.py`, `src/aeat/core/parsing/__init__.py`,
`src/aeat/adapters/outbound/aeat/sede/_notifications.py`,
`src/aeat/adapters/outbound/aeat/sede/_censo.py`,
`src/aeat/domain/deadlines/_profiles.py`
