---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P02.S01'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P02.S01`

Added `dead_end: str | None = None` to `DiagnosticCheck` and wired a
`@model_validator(mode="after")` that rejects setting both
`next_action` and `dead_end` simultaneously.

- Modified: `src/aeat/application/diagnostics.py`

## Description

`DiagnosticCheck` is now the type-system source of truth for the
"always-actionable" contract called out in the config-repair-shape
ADR. The new `dead_end` field documents a terminal failure with no
automated route; the validator enforces that a row picks at most
one road. Empty strings are treated as unset so locale-stripped
values do not slip past the check.

## Confirmation

- `pytest src/aeat/application/test_diagnostics.py` passes 15 tests.
- New contract tests in P02.S03 cover the both-populated rejection.
